import math
import random
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.movies.models import Movie
from apps.movies.services.presentation import MediaContextMixin
from .serializers import RecommendationQuerySerializer, RecommendationSerializer
from .services.hybrid.registry import catalog_snapshot, get_hybrid_service, user_history, watchlist_ids
from .services.preferences import apply_preferences


class RecommendationView(MediaContextMixin, GenericAPIView):
    serializer_class = RecommendationSerializer

    @extend_schema(parameters=[RecommendationQuerySerializer], description="Rank unrated catalog films for the signed-in user. Watchlisted films are excluded by default. Scores are relative ranking signals, not probabilities. Missing model coverage is represented by null, with weights redistributed over available components.")
    def get(self, request):
        params = RecommendationQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        service = get_hybrid_service()
        history = user_history(request.user)
        saved = watchlist_ids(request.user)
        ranked, profile = service.rank(history, catalog_snapshot(), saved if values["exclude_watchlist"] else ())
        ranked, profile = apply_preferences(request.user, history, ranked, profile, service.content, saved)
        limit = values["limit"]
        refresh_seed = values.get("refresh_seed")
        total_candidates = len(ranked)
        if refresh_seed:
            pool_size = min(total_candidates, 72)
            pool = ranked[:pool_size]
            if len(pool) <= limit:
                selected = pool
            else:
                user_id = request.user.pk if request.user.is_authenticated else "anon"
                rng = random.Random(f"{user_id}:{refresh_seed}")
                keys = []
                for entry in pool:
                    w = max(entry.score, 1e-6)
                    u = rng.uniform(1e-7, 1.0)
                    key = math.log(u) / w
                    keys.append((key, entry))
                keys.sort(key=lambda x: x[0], reverse=True)
                selected = [entry for _, entry in keys[:limit]]
                selected.sort(key=lambda entry: (-entry.score, entry.tmdb_id))
        else:
            offset = values.get("offset", 0)
            if total_candidates > 0 and offset >= total_candidates:
                offset = offset % total_candidates
            selected = ranked[offset:offset + limit]
            if len(selected) < limit and total_candidates > len(selected):
                additional = min(limit - len(selected), offset)
                if additional > 0:
                    selected = list(selected) + list(ranked[:additional])
        # One movie query plus one genre prefetch, independent of response size.
        movies = {movie.tmdb_id: movie for movie in Movie.objects.filter(tmdb_id__in=[entry.tmdb_id for entry in selected]).prefetch_related("genres")}
        result = {
            "results": [{"movie": movies[entry.tmdb_id], "score": entry.score, "components": entry.components, "effective_weights": entry.effective_weights, "reasons": getattr(entry, 'reasons', ())} for entry in selected if entry.tmdb_id in movies],
            "profile": profile,
            "models": {"content": service.content is not None, "collaborative": service.collaborative is not None},
            "configured_weights": service.weights,
            "candidate_count": len(ranked),
        }
        response = Response(self.get_serializer(result).data)
        response["Cache-Control"] = "private, no-store"
        return response
