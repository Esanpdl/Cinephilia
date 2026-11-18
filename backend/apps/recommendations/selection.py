from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from apps.movies.models import Movie
from apps.movies.serializers import MovieSummarySerializer
from apps.movies.services.presentation import MediaContextMixin
from .services.hybrid.registry import get_hybrid_service, catalog_snapshot, user_history, watchlist_ids
from .services.from_films import rank_selection
from .services.preferences import taste_catalog
from .services.semantic_discovery import get_discovery_service


class SelectionInput(serializers.Serializer):
    movie_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=3, max_length=10)
    discovery = serializers.ChoiceField(choices=['familiar', 'balanced', 'adventurous'], default='balanced')

    def validate_movie_ids(self, values):
        if len(set(values)) != len(values):
            raise serializers.ValidationError('Select 3–10 different films.')
        if set(Movie.objects.filter(tmdb_id__in=values).values_list('tmdb_id', flat=True)) != set(values):
            raise serializers.ValidationError('Choose films available in this catalogue.')
        return values


class SelectionItem(serializers.Serializer):
    movie = MovieSummarySerializer()
    match_percentage = serializers.IntegerField()
    explanations = serializers.ListField(child=serializers.CharField())
    components = serializers.DictField(child=serializers.FloatField(allow_null=True))
    effective_weights = serializers.DictField(child=serializers.FloatField())


class SelectionOutput(serializers.Serializer):
    discovery = serializers.CharField()
    results = SelectionItem(many=True)
    models = serializers.DictField(child=serializers.BooleanField())
    selected_count = serializers.IntegerField()
    notice = serializers.CharField()
    score_note = serializers.CharField()


class SelectionThrottle(SimpleRateThrottle):
    rate = '20/min'
    scope = 'selection'

    def get_cache_key(self, request, view):
        identity = f'user:{request.user.pk}' if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': identity}


class FromFilmsView(MediaContextMixin, GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SelectionOutput
    throttle_classes = [SelectionThrottle]

    @extend_schema(request=SelectionInput, responses=SelectionOutput,
                   description='Three request-local hybrid recommendations from 3–10 watched and enjoyed films. Never writes ratings or preferences.')
    def post(self, request):
        incoming = SelectionInput(data=request.data)
        incoming.is_valid(raise_exception=True)
        service = get_hybrid_service()
        history = user_history(request.user) if request.user.is_authenticated else {}
        excluded = watchlist_ids(request.user) if request.user.is_authenticated else ()
        result = rank_selection(incoming.validated_data['movie_ids'], [m['tmdb_id'] for m in catalog_snapshot()],
                                get_discovery_service(service.content), service.collaborative, history, excluded,
                                discovery=incoming.validated_data['discovery'], metadata=taste_catalog())
        movies = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=[r['tmdb_id'] for r in result['results']]).prefetch_related('genres')}
        result['results'] = [{**r, 'movie': movies[r['tmdb_id']]} for r in result['results'] if r['tmdb_id'] in movies]
        response = Response(self.get_serializer(result).data)
        response['Cache-Control'] = 'private, no-store'
        return response
