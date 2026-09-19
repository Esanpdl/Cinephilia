from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.movies.models import Movie
from apps.movies.services.presentation import MediaContextMixin
from .serializers import RecommendationQuerySerializer, RecommendationSerializer
from .services.hybrid.registry import catalog_snapshot, get_hybrid_service, user_history, watchlist_ids


class RecommendationView(MediaContextMixin, GenericAPIView):
    serializer_class = RecommendationSerializer

    @extend_schema(parameters=[RecommendationQuerySerializer], description="Rank unrated catalog films for the signed-in user. Watchlisted films are excluded by default. Scores are relative ranking signals, not probabilities. Missing model coverage is represented by null, with weights redistributed over available components.")
    def get(self, request):
        params = RecommendationQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        service = get_hybrid_service()
        ranked, profile = service.rank(user_history(request.user), catalog_snapshot(), watchlist_ids(request.user) if values["exclude_watchlist"] else ())
        # One movie query plus one genre prefetch, independent of response size.
        selected = ranked[:values["limit"]]
        movies = {movie.tmdb_id: movie for movie in Movie.objects.filter(tmdb_id__in=[entry.tmdb_id for entry in selected]).prefetch_related("genres")}
        result = {
            "results": [{"movie": movies[entry.tmdb_id], "score": entry.score, "components": entry.components, "effective_weights": entry.effective_weights} for entry in selected if entry.tmdb_id in movies],
            "profile": profile,
            "models": {"content": service.content is not None, "collaborative": service.collaborative is not None},
            "configured_weights": service.weights,
            "candidate_count": len(ranked),
        }
        response = Response(self.get_serializer(result).data)
        response["Cache-Control"] = "private, no-store"
        return response
