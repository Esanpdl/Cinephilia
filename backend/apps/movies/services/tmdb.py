"""TMDB transport, persistent JSON cache and bounded retries, independent of views."""
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from django.conf import settings
import requests


class TMDBError(RuntimeError):
    pass


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class TMDBClient:
    base_url = "https://api.themoviedb.org/3"

    def __init__(self, token=None, language=None, cache_dir=None, api_key=None):
        self.token = token or settings.TMDB_READ_ACCESS_TOKEN
        self.api_key = api_key or settings.TMDB_API_KEY
        if not self.token and not self.api_key:
            raise TMDBError("Set TMDB_READ_ACCESS_TOKEN or TMDB_API_KEY in backend/.env before fetching movie data.")
        self.language = language or settings.TMDB_LANGUAGE
        self.cache_dir = Path(cache_dir or settings.TMDB_DATA_DIR / "cache")
        self.local = threading.local()
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.sessions = []
        if settings.TMDB_REQUESTS_PER_SECOND <= 0:
            raise TMDBError("TMDB_REQUESTS_PER_SECOND must be positive.")

    def close(self):
        for session in self.sessions:
            session.close()

    def _session(self):
        if not hasattr(self.local, "session"):
            session = requests.Session()
            session.headers.update({"Accept": "application/json"})
            if self.token:
                session.headers["Authorization"] = f"Bearer {self.token}"
            self.local.session = session
            with self.lock:
                self.sessions.append(session)
        return self.local.session

    def _throttle(self):
        with self.lock:
            now = time.monotonic()
            wait = max(0, self.next_request - now)
            self.next_request = max(now, self.next_request) + 1 / settings.TMDB_REQUESTS_PER_SECOND
        if wait:
            time.sleep(wait)

    def get(self, path, params=None, refresh=False):
        params = params or {}
        fingerprint = hashlib.sha256(json.dumps([path, params], sort_keys=True).encode()).hexdigest()
        cached_path = self.cache_dir / f"{fingerprint}.json"
        if not refresh and cached_path.exists():
            try:
                cached = json.loads(cached_path.read_text(encoding="utf-8"))
                if time.time() - cached["fetched_at"] < settings.TMDB_CACHE_TTL:
                    return cached["payload"]
            except (ValueError, KeyError, OSError):
                pass  # A damaged cache is replaced only with a new authentic response.
        for attempt in range(5):
            self._throttle()
            try:
                request_params = dict(params)
                if not self.token:
                    request_params["api_key"] = self.api_key
                response = self._session().get(self.base_url + path, params=request_params, timeout=(10, 30))
            except requests.RequestException:
                if attempt == 4:
                    raise TMDBError(f"TMDB network request failed for {path}; retry the import to resume.") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                wait = 2 ** attempt
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = max(wait, float(retry_after))
                    except ValueError:
                        try:
                            wait = max(wait, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError):
                            pass
                if attempt == 4 or wait > 60:
                    raise TMDBError(f"TMDB returned HTTP {response.status_code}; retry after {wait:.0f} seconds.")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                raise TMDBError(f"TMDB returned HTTP {response.status_code} for {path}; import stopped without substituting data.")
            try:
                payload = response.json()
            except ValueError:
                raise TMDBError(f"TMDB returned invalid JSON for {path}.") from None
            if not isinstance(payload, dict):
                raise TMDBError(f"TMDB returned an unexpected response shape for {path}.")
            write_json(cached_path, {"fetched_at": time.time(), "payload": payload})
            return payload
        raise TMDBError("TMDB retry limit reached.")

    def discover(self, page, min_votes, min_rating, release_before=None, refresh=False):
        if not 1 <= page <= 500:
            raise TMDBError("TMDB discovery only permits pages 1–500.")
        return self.get("/discover/movie", {
            "page": page,
            "language": self.language,
            "sort_by": "vote_average.desc",
            "vote_count.gte": min_votes,
            "vote_average.gte": min_rating,
            "include_adult": "false",
            "include_video": "false",
            "primary_release_date.lte": release_before or date.today().isoformat(),
        }, refresh=refresh)

    def details(self, movie_id, refresh=False):
        if not isinstance(movie_id, int) or movie_id <= 0:
            raise TMDBError("TMDB movie ID must be a positive integer.")
        return self.get(f"/movie/{movie_id}", {
            "language": self.language,
            "append_to_response": "credits,keywords,videos",
        }, refresh=refresh)

    def configuration(self):
        return self.get("/configuration")

    def search_movies(self, title, page=1, year=None):
        params = {
            "query": title, "page": page, "include_adult": "false",
            "language": self.language,
        }
        if year is not None:
            params["year"] = year
        return self.get("/search/movie", params)

    def alternative_titles(self, movie_id):
        return self.get(f"/movie/{movie_id}/alternative_titles")
