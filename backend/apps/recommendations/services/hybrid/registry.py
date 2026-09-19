import logging
from django.conf import settings
from django.core.cache import cache
from apps.movies.models import Movie
from apps.ratings.models import Rating, WatchlistItem
from ..content.contracts import ContentIndexError
from ..content.registry import get_content_service
from ..collaborative.contracts import CollaborativeModelError
from ..collaborative.registry import get_collaborative_service
from .engine import HybridService

logger = logging.getLogger(__name__)


def get_hybrid_service():
    content = collaborative = None
    if settings.HYBRID_WEIGHTS["content"]:
        try:
            content = get_content_service()
        except ContentIndexError:
            logger.warning("Content artifact unavailable; hybrid will use the available components.")
    if settings.HYBRID_WEIGHTS["collaborative"]:
        try:
            collaborative = get_collaborative_service()
        except CollaborativeModelError:
            logger.warning("Collaborative artifact unavailable; hybrid will use the available components.")
    return HybridService(content, collaborative, settings.HYBRID_WEIGHTS, settings.HYBRID_MIN_LIKED_RATING, settings.HYBRID_MAX_CONTENT_SEEDS)


def catalog_snapshot():
    key = "hybrid:catalog:v1"
    catalog = cache.get(key)
    if catalog is None:
        catalog = list(Movie.objects.order_by("tmdb_id").values("tmdb_id", "popularity"))
        cache.set(key, catalog, settings.HYBRID_CATALOG_CACHE_SECONDS)
    return catalog


def user_history(user):
    return dict(Rating.objects.filter(user=user).order_by("-updated_at", "-pk").values_list("movie__tmdb_id", "score"))


def watchlist_ids(user):
    return set(WatchlistItem.objects.filter(user=user).values_list("movie__tmdb_id", flat=True))
