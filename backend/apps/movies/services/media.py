"""Build embeddable URLs from authentic TMDB metadata; absent media stays absent."""
import re
from urllib.parse import quote, urlsplit

from .tmdb import TMDBError

VIDEO_KEY = re.compile(r"^[A-Za-z0-9_-]{11}$")


def select_trailer(videos, language="en-US"):
    candidates = [video for video in videos if (
        video.get("site") == "YouTube"
        and video.get("type") == "Trailer"
        and VIDEO_KEY.fullmatch(video.get("key", ""))
    )]
    preferred = language.split("-")[0]
    candidates.sort(key=lambda video: (
        video.get("iso_639_1") == preferred,
        bool(video.get("official")),
        video.get("published_at") or "",
        video["key"],
    ), reverse=True)
    return candidates[0] if candidates else None


def trailer_embed_url(key):
    return f"https://www.youtube.com/embed/{key}" if key and VIDEO_KEY.fullmatch(key) else None


def image_url(path, configuration, kind="poster", preferred_size="w500"):
    if not path:
        return None
    images = configuration.get("images", {})
    base = images.get("secure_base_url", "")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or parsed.netloc != "image.tmdb.org":
        raise TMDBError("TMDB configuration has an unexpected secure image base URL.")
    sizes = images.get(f"{kind}_sizes", [])
    size = preferred_size if preferred_size in sizes else "original"
    if size not in sizes or not path.startswith("/") or path.startswith("//") or ".." in path:
        raise TMDBError("TMDB image path or supported sizes are invalid.")
    return f"{base.rstrip('/')}/{size}{quote(path, safe='/')}"
