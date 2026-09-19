from django.conf import settings
from django.core.checks import Error, register
from .services.hybrid.engine import HybridService


@register()
def hybrid_configuration(app_configs, **kwargs):
    try:
        HybridService(None, None, settings.HYBRID_WEIGHTS, settings.HYBRID_MIN_LIKED_RATING, settings.HYBRID_MAX_CONTENT_SEEDS)
        if settings.HYBRID_CATALOG_CACHE_SECONDS < 0:
            raise ValueError("Catalog cache duration must be nonnegative.")
    except (TypeError, ValueError) as error:
        return [Error(str(error), id="recommendations.E001")]
    return []
