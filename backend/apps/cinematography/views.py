from collections import Counter
from datetime import timedelta
from pathlib import Path
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiTypes
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from apps.movies.models import Movie
from .models import TrailerAnalysis, Technique, StudyCard, TechniqueSubmission
from .serializers import (AnalysisSummarySerializer, AnalysisDetailSerializer, TechniqueSerializer, CardSerializer,
                          StudentQuerySerializer, CompareQuerySerializer, TagSerializer, TagWriteSerializer,
                          ModerationSerializer, QuizAnswerSerializer)
from .services.learning import analyses, palette_similarity, weekly_choice, week_key


@extend_schema(parameters=[StudentQuerySerializer])
class StudentFilmsView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    def get_queryset(self):
        params = StudentQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        queryset = TrailerAnalysis.objects.select_related('movie').defer('vector')
        if values.get('q'):
            queryset = queryset.filter(movie__title__icontains=values['q'])
        if values.get('status'):
            queryset = queryset.filter(status=values['status'])
        if values.get('color_mode'):
            queryset = queryset.filter(status='ready', color_mode=values['color_mode'])
        if values.get('technique'):
            queryset = queryset.filter(Q(status='ready', study_cards__technique__slug=values['technique'], study_cards__approved=True) |
                                       Q(movie__technique_submissions__technique__slug=values['technique'], movie__technique_submissions__status='approved')).distinct()
        return queryset


class StudentFilmView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisDetailSerializer
    lookup_field = 'movie__tmdb_id'
    lookup_url_kwarg = 'tmdb_id'

    def get_queryset(self):
        return analyses()


class TaxonomyView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TechniqueSerializer
    pagination_class = None
    queryset = Technique.objects.all()


@extend_schema(parameters=[StudentQuerySerializer])
class CardsView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CardSerializer

    def get_queryset(self):
        params = StudentQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        queryset = StudyCard.objects.filter(approved=True, analysis__status='ready').select_related('analysis__movie', 'technique')
        if params.validated_data.get('technique'):
            queryset = queryset.filter(technique__slug=params.validated_data['technique'])
        if params.validated_data.get('q'):
            queryset = queryset.filter(analysis__movie__title__icontains=params.validated_data['q'])
        return queryset


class CompareView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CompareQuerySerializer

    @extend_schema(parameters=[CompareQuerySerializer], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        params = self.get_serializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        ids = [params.validated_data['left'], params.validated_data['right']]
        records = {a.movie.tmdb_id: a for a in analyses().filter(movie__tmdb_id__in=ids)}
        if len(records) != 2:
            raise Http404('Both films must belong to the selected 500.')
        left, right = [records[mid] for mid in ids]
        available = left.status == right.status == 'ready'
        shared = sorted({c.technique.slug for c in left.study_cards.all()} & {c.technique.slug for c in right.study_cards.all()}) if available else []
        # Batch vector lookup avoids deferred-field N+1 queries.
        vectors = dict(TrailerAnalysis.objects.filter(pk__in=[left.pk, right.pk]).values_list('pk', 'vector')) if available else {}
        return Response({'left': AnalysisDetailSerializer(left).data, 'right': AnalysisDetailSerializer(right).data,
                         'palette_similarity': palette_similarity(vectors[left.pk], vectors[right.pk]) if available else None,
                         'metric_difference': {k: round(left.metrics[k] - right.metrics[k], 4) for k in ['brightness', 'saturation', 'contrast']} if available else {},
                         'shared_observations': shared, 'similarity_scope': 'Color histogram overlap only; not narrative, editing or overall film quality.'})


class SimilarView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, tmdb_id):
        target = get_object_or_404(TrailerAnalysis, movie__tmdb_id=tmdb_id)
        if target.status != 'ready':
            return Response({'results': [], 'reason': 'A validated source analysis is required.'})
        scores = [(mid, palette_similarity(target.vector, vector)) for mid, vector in TrailerAnalysis.objects.filter(status='ready').exclude(pk=target.pk).values_list('movie__tmdb_id', 'vector')]
        scores = sorted((s for s in scores if s[1] is not None), key=lambda s: (-s[1], s[0]))[:8]
        records = {a.movie.tmdb_id: a for a in TrailerAnalysis.objects.select_related('movie').filter(movie__tmdb_id__in=[mid for mid, _ in scores])}
        return Response({'results': [{**AnalysisSummarySerializer(records[mid]).data, 'palette_similarity': score} for mid, score in scores], 'scope': 'Similarity of sampled source colors only.'})


class OverviewView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        values = list(TrailerAnalysis.objects.values('status', 'color_mode', 'metrics', 'movie__tmdb_id', 'movie__title'))
        ready = [r for r in values if r['status'] == 'ready']
        return Response({'selected': len(values), 'status_counts': dict(Counter(r['status'] for r in values)),
                         'color_counts': dict(Counter(r['color_mode'] for r in ready)),
                         'scatter': [{'tmdb_id': r['movie__tmdb_id'], 'title': r['movie__title'], **r['metrics']} for r in ready],
                         'technique_counts': list(StudyCard.objects.filter(approved=True, analysis__status='ready').values('technique__name').annotate(count=Count('analysis_id', distinct=True)).order_by('-count')),
                         'scope': 'Available source analyses; unavailable films are excluded from charts.'})


class SpotlightView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisDetailSerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        ids = list(TrailerAnalysis.objects.filter(status='ready', study_cards__approved=True).values_list('movie__tmdb_id', flat=True).distinct())
        mid = weekly_choice(ids, timezone.localdate())
        return Response({'week': week_key(timezone.localdate()), 'film': AnalysisDetailSerializer(analyses().get(movie__tmdb_id=mid)).data if mid else None})


class QuizView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = QuizAnswerSerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        cards = list(StudyCard.objects.filter(approved=True, analysis__status='ready').select_related('analysis__movie', 'technique')[:500])
        if not cards:
            return Response({'question': None})
        import secrets
        card = secrets.choice(cards)
        alternatives = list(Technique.objects.filter(automatic=card.technique.automatic).exclude(pk=card.technique_id))
        options = [card.technique] + secrets.SystemRandom().sample(alternatives, min(3, len(alternatives)))
        secrets.SystemRandom().shuffle(options)
        return Response({'question': {'card_id': card.pk, 'image_url': CardSerializer(card).data['image_url'],
                         'prompt': card.explanation + ' Which term best matches this observation?',
                         'options': [{'slug': t.slug, 'name': t.name} for t in options]}})

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def post(self, request):
        params = self.get_serializer(data=request.data)
        params.is_valid(raise_exception=True)
        card = get_object_or_404(StudyCard.objects.select_related('analysis__movie', 'technique'), pk=params.validated_data['card_id'], approved=True, analysis__status='ready')
        return Response({'correct': params.validated_data['answer'] == card.technique.slug, 'card': CardSerializer(card).data})


class TagsView(ListAPIView):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TechniqueSubmission.objects.filter(user=self.request.user).select_related('movie', 'technique')

    @extend_schema(request=TagWriteSerializer, responses={201: TagSerializer})
    def post(self, request):
        incoming = TagWriteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = dict(incoming.validated_data)
        movie = get_object_or_404(Movie, tmdb_id=data.pop('tmdb_id'))
        with transaction.atomic():
            # Serialize quotas/duplicate checks for this user, including concurrent requests.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if TechniqueSubmission.objects.filter(user=request.user, created_at__gte=timezone.now() - timedelta(days=1)).count() >= 20:
                raise ValidationError('At most 20 technique submissions per day.')
            if TechniqueSubmission.objects.filter(user=request.user, movie=movie, technique=data['technique']).exists():
                raise ValidationError('You have already submitted this technique for this film.')
            obj = TechniqueSubmission.objects.create(user=request.user, movie=movie, **data)
        return Response(TagSerializer(obj).data, status=201)


class PublicTagsView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TagSerializer

    def get_queryset(self):
        movie = get_object_or_404(Movie, tmdb_id=self.kwargs['tmdb_id'])
        return TechniqueSubmission.objects.filter(movie=movie, status='approved').select_related('movie', 'technique')


class ModerationQueueView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TagSerializer

    def get_queryset(self):
        return TechniqueSubmission.objects.filter(status='pending').select_related('movie', 'technique')


class ModerateTagView(GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ModerationSerializer

    @extend_schema(responses=TagSerializer)
    def patch(self, request, pk):
        params = self.get_serializer(data=request.data)
        params.is_valid(raise_exception=True)
        with transaction.atomic():
            obj = get_object_or_404(TechniqueSubmission.objects.select_for_update().select_related('movie', 'technique'), pk=pk)
            obj.status = params.validated_data['status']
            obj.moderation_note = params.validated_data.get('note', '')
            obj.moderator, obj.reviewed_at = request.user, timezone.now()
            obj.save(update_fields=['status', 'moderation_note', 'moderator', 'reviewed_at'])
        return Response(TagSerializer(obj).data)


class FrameView(GenericAPIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={(200, 'image/jpeg'): OpenApiTypes.BINARY})
    def get(self, request, tmdb_id, digest, filename):
        if not re.fullmatch(r'[a-f0-9]{12}', digest) or not re.fullmatch(r'\d{3}\.jpg', filename):
            raise Http404
        image = f'{tmdb_id}/{digest}/{filename}'
        analysis = get_object_or_404(TrailerAnalysis, movie__tmdb_id=tmdb_id, status='ready', source_sha256__startswith=digest)
        if image not in {f['image'] for f in analysis.frames} and not analysis.study_cards.filter(image=image, approved=True).exists():
            raise Http404
        root = (settings.BASE_DIR.parent / 'data/phase8/frames').resolve()
        path = (root / image).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise Http404
        response = FileResponse(path.open('rb'), content_type='image/jpeg')
        response['Cache-Control'] = 'public, max-age=86400'
        response['ETag'] = '"' + digest + '-' + filename + '"'
        return response
