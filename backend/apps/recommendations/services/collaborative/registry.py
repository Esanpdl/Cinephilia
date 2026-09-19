from functools import lru_cache
import json
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string

from .artifacts import digest, write_json
from .contracts import CollaborativeModelError
from .engine import SVDService, valid_id


@lru_cache(maxsize=1)
def _load(service_class, directory, checksum):
    if digest(Path(directory) / "manifest.json") != checksum:
        raise CollaborativeModelError("Collaborative manifest changed; reactivate a verified artifact.")
    return import_string(service_class)(directory)


def get_collaborative_service():
    try:
        pointer = json.loads(Path(settings.COLLABORATIVE_MODEL_POINTER).read_text(encoding="utf-8"))
        return _load(settings.COLLABORATIVE_SERVICE_CLASS, pointer["directory"], pointer["manifest_sha256"])
    except (OSError, ValueError, KeyError) as error:
        raise CollaborativeModelError("No usable collaborative model is active. Run activate_collaborative_model.") from error


def activate(directory, pointer_path):
    directory = Path(directory).resolve()
    service = SVDService(directory)
    write_json(pointer_path, {"directory": str(directory), "manifest_sha256": digest(directory / "manifest.json"), "catalog_sha256": service.manifest["catalog_sha256"]})
    _load.cache_clear()
    return service.manifest


def history_for_user(user_id):
    """Only Django rating rows; never interpret this ID as a MovieLens user ID."""
    from apps.ratings.models import Rating
    valid_id(user_id)
    return dict(Rating.objects.filter(user_id=user_id).values_list("movie__tmdb_id", "score"))
