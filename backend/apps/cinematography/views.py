from config.public_cache import PublicReadCacheMixin, cached_public_get
from collections import Counter
from datetime import timedelta
from pathlib import Path
import re

from django.conf import settings
from django.core.cache import cache
from config.public_cache import revision
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.fields.json import KeyTransform
from django.http import FileResponse, Http404, HttpResponseNotModified
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
                          ModerationSerializer, QuizAnswerSerializer, PublishedCardSerializer)
from .services.learning import analyses, palette_index, palette_similarity, weekly_choice, week_key, observation_slugs, visual_similarity, model_observation_slugs
from .services.frame_matching import matched_frames
from .services.study_catalog import taxonomy, published_cards, filter_cards, COLOUR_TERMS
from .services.colour_distance import load_signature
from .services.learning import visual_candidates


class FilmOptionsView(PublicReadCacheMixin, GenericAPIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @cached_public_get
    def get(self, request):
        rows = TrailerAnalysis.objects.order_by('movie__title', 'movie__tmdb_id').values_list('movie__tmdb_id', 'movie__title', 'movie__release_date')
        results = [{'tmdb_id': mid, 'title': title, 'year': date.year if date else None} for mid, title, date in rows]
        return Response({'count': len(results), 'results': results})


@extend_schema(parameters=[StudentQuerySerializer])
class StudentFilmsView(PublicReadCacheMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    def get_queryset(self):
        params = StudentQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        queryset = TrailerAnalysis.objects.select_related('movie').annotate(preview_frame=KeyTransform('0', 'frames')).only(
            'movie_id', 'movie__tmdb_id', 'movie__title', 'movie__release_date', 'movie__poster_path',
            'selection_rank', 'status', 'reason', 'color_mode', 'palette')
        if values.get('q'):
            queryset = queryset.filter(movie__title__icontains=values['q'])
        if values.get('status'):
            queryset = queryset.filter(status=values['status'])
        if values.get('color_mode'):
            queryset = queryset.filter(status='ready', color_mode=values['color_mode'])
        if values.get('technique'):
            cards = Q(status='ready', study_cards__technique__slug=values['technique'], study_cards__approved=True)
            cards &= (~Q(version='supplied-stills-2') | Q(study_cards__evidence='reviewed'))
            queryset = queryset.filter(cards | Q(status='ready', quality__measured_observation_slugs__contains=[values['technique']]) |
                                       Q(status='ready', quality__human_observation_slugs__contains=[values['technique']]) |
                                       Q(status='ready', quality__model_observation_slugs__contains=[values['technique']]) |
                                       Q(movie__technique_submissions__technique__slug=values['technique'], movie__technique_submissions__status='approved')).distinct()
        return queryset


class StudentFilmView(PublicReadCacheMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisDetailSerializer
    lookup_field = 'movie__tmdb_id'
    lookup_url_kwarg = 'tmdb_id'

    def get_queryset(self):
        return analyses()


class TaxonomyView(PublicReadCacheMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TechniqueSerializer
    pagination_class = None
    queryset = Technique.objects.all()

    def list(self, request, *args, **kwargs):
        return Response(sorted(taxonomy().values(), key=lambda t: (t['category'], t['name'])))


@extend_schema(parameters=[StudentQuerySerializer])
class CardsView(PublicReadCacheMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublishedCardSerializer

    def list(self, request, *args, **kwargs):
        params = StudentQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        cards = filter_cards(published_cards(), **{key: values[key] for key in ('source', 'category', 'technique', 'q') if key in values})
        page = self.paginate_queryset(cards)
        return self.get_paginated_response(page)

    def get_queryset(self):
        params = StudentQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        queryset = StudyCard.objects.filter(approved=True, analysis__status='ready').select_related('analysis__movie', 'technique')
        if params.validated_data.get('technique'):
            queryset = queryset.filter(technique__slug=params.validated_data['technique'])
        if params.validated_data.get('q'):
            queryset = queryset.filter(analysis__movie__title__icontains=params.validated_data['q'])
        return queryset


class CompareView(PublicReadCacheMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CompareQuerySerializer

    @extend_schema(parameters=[CompareQuerySerializer], responses=OpenApiTypes.OBJECT)
    @cached_public_get
    def get(self, request):
        params = self.get_serializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        ids = [params.validated_data['left'], params.validated_data['right']]
        records = {a.movie.tmdb_id: a for a in analyses().filter(movie__tmdb_id__in=ids)}
        if len(records) != 2:
            raise Http404('Both films must belong to the film-analysis collection.')
        left, right = [records[mid] for mid in ids]
        available = left.status == right.status == 'ready'
        left_terms, right_terms = observation_slugs(left), observation_slugs(right)
        shared = sorted(left_terms & right_terms)
        # Batch vector lookup avoids deferred-field N+1 queries.
        signatures = [load_signature(settings.BASE_DIR.parent, a.movie.tmdb_id, a.source_sha256, a.quality.get('palette_method')) for a in (left, right)] if available else []
        palette = palette_similarity(*[d['film'] if d is not None else None for d in signatures]) if available else None
        matching = matched_frames(left, right)
        details = [dict(AnalysisDetailSerializer(film).data) for film in (left, right)]
        for side, detail in zip(('left', 'right'), details):
            detail['frames'] = [p[side] for p in matching['pairs']]
        return Response({'left': details[0], 'right': details[1], 'frame_matching': matching,
                         'palette_similarity': palette,
                         'style_similarity': visual_similarity(palette, left_terms, right_terms, model_observation_slugs(left), model_observation_slugs(right)),
                         'left_observations': TagSerializer(left.movie.published_observations, many=True).data,
                         'right_observations': TagSerializer(right.movie.published_observations, many=True).data,
                         'metric_difference': {k: round(left.metrics[k] - right.metrics[k], 4) for k in ['brightness', 'saturation', 'contrast']} if available else {},
                         'shared_observations': shared, 'similarity_scope': 'Perceptual colour-distribution similarity across all supplied frames. Not a probability or a measure of narrative, editing or film quality.'})


class SimilarView(PublicReadCacheMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @cached_public_get
    def get(self, request, tmdb_id):
        target = get_object_or_404(analyses(), movie__tmdb_id=tmdb_id)
        if target.status != 'ready':
            return Response({'results': [], 'reason': 'A validated source analysis is required.'})
        vectors = dict(palette_index())
        target_terms = observation_slugs(target)
        target_model = model_observation_slugs(target)
        scores = []
        for candidate, terms, candidate_model in visual_candidates():
            if candidate.movie.tmdb_id == tmdb_id:
                continue
            palette = palette_similarity(vectors.get(tmdb_id), vectors.get(candidate.movie.tmdb_id))
            style = visual_similarity(palette, target_terms, terms, target_model, candidate_model)
            if style['score'] is not None:
                scores.append((candidate, palette, style, sorted(target_terms & terms)))
        scores.sort(key=lambda row: (-row[2]['score'], row[0].movie.tmdb_id))
        return Response({'results': [{**AnalysisSummarySerializer(candidate).data,
                                      'palette_similarity': palette, 'style_similarity': style,
                                      'shared_observations': shared}
                                     for candidate, palette, style, shared in scores[:8]],
                         'scope': 'Source-frame colour distributions and published technique evidence; missing technique evidence is not treated as absence.'})


class OverviewView(PublicReadCacheMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisSummarySerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @cached_public_get
    def get(self, request):
        values = list(TrailerAnalysis.objects.values('status', 'color_mode', 'metrics', 'movie__tmdb_id', 'movie__title'))
        ready = [r for r in values if r['status'] == 'ready']
        return Response({'selected': len(values), 'status_counts': dict(Counter(r['status'] for r in values)),
                         'color_counts': dict(Counter(r['color_mode'] for r in ready)),
                         'scatter': [{'tmdb_id': r['movie__tmdb_id'], 'title': r['movie__title'], **r['metrics']} for r in ready],
                         'technique_counts': list(StudyCard.objects.filter(approved=True, analysis__status='ready').values('technique__name').annotate(count=Count('analysis_id', distinct=True)).order_by('-count')),
                         'reviewed_technique_counts': list(TechniqueSubmission.objects.filter(status='approved').values('technique__name', 'technique__slug').annotate(count=Count('movie_id', distinct=True)).order_by('-count', 'technique__slug')),
                         'scope': 'Available source analyses; unavailable films are excluded from charts.'})


class SpotlightView(PublicReadCacheMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = AnalysisDetailSerializer

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @cached_public_get
    def get(self, request):
        ids = list(TrailerAnalysis.objects.filter(status='ready', study_cards__approved=True).values_list('movie__tmdb_id', flat=True).distinct())
        mid = weekly_choice(ids, timezone.localdate())
        return Response({'week': week_key(timezone.localdate()), 'film': AnalysisDetailSerializer(analyses().get(movie__tmdb_id=mid)).data if mid else None})


class QuizView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = QuizAnswerSerializer

    def get_authenticators(self):
        return [] if getattr(self.request, 'method', None) == 'GET' else super().get_authenticators()

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        params = StudentQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        eligible = filter_cards([c for c in published_cards() if c['evidence'] != 'model'], category=params.validated_data['category'])
        previous = request.query_params.get('previous', '')
        eligible = [c for c in eligible if str(c['id']) != previous]
        if not eligible:
            return Response({'question': None})
        import secrets
        # Balance technique coverage so large colour classes do not dominate All.
        by_term = {}
        for item in eligible:
            by_term.setdefault(item['technique']['slug'], []).append(item)
        slug = secrets.choice(list(by_term))
        card = secrets.choice(by_term[slug])
        terms = taxonomy()
        alternatives = [t for key, t in terms.items() if key != slug and (key in COLOUR_TERMS) == (slug in COLOUR_TERMS)]
        options = [card['technique']] + secrets.SystemRandom().sample(alternatives, min(3, len(alternatives)))
        secrets.SystemRandom().shuffle(options)
        return Response({'question': {'card_id': card['id'], 'image_url': card['image_url'],
                         'prompt': card['technique']['description'] + ' Which term best matches this observation?',
                         'options': [{'slug': t['slug'], 'name': t['name']} for t in options]}})

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def post(self, request):
        params = self.get_serializer(data=request.data)
        params.is_valid(raise_exception=True)
        card = next((c for c in published_cards() if str(c['id']) == params.validated_data['card_id'] and c['evidence'] != 'model'), None)
        if card is None:
            raise Http404('This reviewed or measured quiz observation is no longer available.')
        return Response({'correct': params.validated_data['answer'] == card['technique']['slug'], 'card': card})


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
        return TechniqueSubmission.objects.filter(movie=movie, status='approved').select_related('movie', 'technique').order_by('-reviewed_at', '-pk')


@extend_schema(parameters=[StudentQuerySerializer])
class ObservationsView(ListAPIView):
    """Reviewed technique evidence across the entire catalog, including non-CV films."""
    permission_classes = [AllowAny]
    serializer_class = TagSerializer

    def get_queryset(self):
        params = StudentQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        queryset = TechniqueSubmission.objects.filter(status='approved').select_related('movie', 'technique')
        if params.validated_data.get('technique'):
            queryset = queryset.filter(technique__slug=params.validated_data['technique'])
        if params.validated_data.get('q'):
            queryset = queryset.filter(movie__title__icontains=params.validated_data['q'])
        return queryset


class ModerationQueueView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TagSerializer

    def get_queryset(self):
        return TechniqueSubmission.objects.filter(status='pending').select_related('movie', 'technique').order_by('created_at', 'pk')


class ModerateTagView(GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ModerationSerializer

    @extend_schema(responses=TagSerializer)
    def patch(self, request, pk):
        params = self.get_serializer(data=request.data)
        params.is_valid(raise_exception=True)
        with transaction.atomic():
            obj = get_object_or_404(TechniqueSubmission.objects.select_for_update().select_related('movie', 'technique'), pk=pk)
            if 'expected_status' in params.validated_data and obj.status != params.validated_data['expected_status']:
                return Response({'detail': 'This submission has already been reviewed. Refresh the queue.'}, status=409)
            obj.status = params.validated_data['status']
            obj.moderation_note = params.validated_data.get('note', '')
            obj.moderator, obj.reviewed_at = request.user, timezone.now()
            obj.save(update_fields=['status', 'moderation_note', 'moderator', 'reviewed_at'])
        return Response(TagSerializer(obj).data)


class FrameView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={(200, 'image/jpeg'): OpenApiTypes.BINARY})
    def get(self, request, tmdb_id, digest, filename):
        if not re.fullmatch(r'[a-f0-9]{12}', digest) or not re.fullmatch(r'\d{3,}\.(?:jpg|jpeg|png|webp)', filename):
            raise Http404
        image = f'{tmdb_id}/{digest}/{filename}'
        key = f'frame-access-v1:{revision()}:{tmdb_id}:{digest}'
        access = cache.get(key)
        if access is None:
            analysis = get_object_or_404(TrailerAnalysis.objects.only('frames', 'quality'), movie__tmdb_id=tmdb_id, status='ready', source_sha256__startswith=digest)
            stills = analysis.quality.get('source_kind') == 'owner-supplied-stills'
            access = {'stills': stills, 'frames': {f['image']: f.get('frame_id') for f in analysis.frames}}
            if not stills:
                access['frames'].update({name: None for name in analysis.study_cards.filter(approved=True).values_list('image', flat=True)})
            cache.set(key, access, 60)
        if image not in access['frames']:
            raise Http404
        if not access['stills'] or not access['frames'][image]:
            raise Http404
        root = (settings.BASE_DIR.parent / 'data/film_frames').resolve()
        path = (settings.BASE_DIR.parent / access['frames'][image]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise Http404
        etag = f'"{digest}-{filename}-{path.stat().st_mtime_ns}"'
        if request.headers.get('If-None-Match') == etag:
            response = HttpResponseNotModified()
            response['ETag'] = etag
            response['Cache-Control'] = 'public, max-age=86400'
            return response
        content_type = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[path.suffix.lower()]
        response = FileResponse(path.open('rb'), content_type=content_type)
        response['Cache-Control'] = 'public, max-age=86400'
        response['ETag'] = etag
        return response
