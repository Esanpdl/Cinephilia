"""Load one immutable artifact per process; reload after atomic activation."""
from functools import lru_cache
import json
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string

from .artifacts import sha256_file, write_json
from .contracts import ContentIndexError
from .engine import TfidfContentService


@lru_cache(maxsize=1)
def _load(service_class, directory, manifest_hash):
    if sha256_file(Path(directory) / "manifest.json") != manifest_hash:
        raise ContentIndexError("Active content index manifest has changed. Reactivate a verified artifact.")
    return import_string(service_class)(directory)


def get_content_service():
    try:
        pointer = json.loads(Path(settings.CONTENT_INDEX_POINTER).read_text(encoding="utf-8"))
        directory = Path(pointer['directory'])
        if not directory.is_absolute():
            directory = Path(settings.CONTENT_INDEX_POINTER).parent / directory
        return _load(settings.CONTENT_SERVICE_CLASS, str(directory.resolve()), pointer["manifest_sha256"])
    except (OSError, ValueError, KeyError) as error:
        raise ContentIndexError("No usable content index is active. Run activate_content_index first.") from error


def activate(directory, pointer_path):
    directory = Path(directory).resolve()
    # Load all arrays and verify dimensions/checksums before changing the pointer.
    service = TfidfContentService(directory)
    try:
        stored_directory = directory.relative_to(Path(pointer_path).resolve().parent).as_posix()
    except ValueError:
        stored_directory = str(directory)
    write_json(pointer_path, {
        "directory": stored_directory,
        "manifest_sha256": sha256_file(directory / "manifest.json"),
        "catalog_sha256": service.manifest["catalog_sha256"],
    })
    _load.cache_clear()
    return service.manifest
