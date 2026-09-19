from functools import lru_cache
import json
from django.conf import settings
from rest_framework.exceptions import APIException


class CatalogNotReady(APIException):
    status_code = 503
    default_detail = "Movie media configuration is not ready. Run the TMDB catalog import."


@lru_cache(maxsize=1)
def _read_configuration(path, modified_ns):
    return json.loads(path.read_text(encoding="utf-8"))


def media_context():
    path = settings.TMDB_DATA_DIR / "configuration.json"
    try:
        return {"tmdb_configuration": _read_configuration(path, path.stat().st_mtime_ns)}
    except (OSError, ValueError):
        raise CatalogNotReady() from None


class MediaContextMixin:
    def get_serializer_context(self):
        return {**super().get_serializer_context(), **media_context()}
