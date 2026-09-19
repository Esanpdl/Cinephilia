"""Integration checks against authentic imported films; test writes are rolled back.

Run after an import. Does not create/drop a test database on hosted Supabase.
"""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.test import Client

from apps.movies.models import Genre, Movie, MovieCredit, Person
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.catalog import normalize_details, upsert_movies
from apps.movies.services.media import trailer_embed_url
from apps.movies.services.queries import movie_details_queryset
from apps.movies.services.tmdb import TMDBClient, write_json
from apps.ratings.models import Rating, WatchlistItem
from apps.users.services.profiles import get_or_create_profile


def rejects(operation):
    try:
        with transaction.atomic():
            operation()
    except IntegrityError:
        return
    raise AssertionError("Database did not reject an invalid or duplicate record.")


def main():
    fixture = settings.TMDB_DATA_DIR / "verification" / "movie-details.json"
    if not fixture.exists():
        first = Movie.objects.filter(catalog_rank__isnull=False).order_by("catalog_rank").first()
        if first is None:
            raise SystemExit("Import the TMDB catalog before running integration verification.")
        client = TMDBClient()
        try:
            write_json(fixture, client.details(first.tmdb_id))
        finally:
            client.close()
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    item = normalize_details(payload, settings.TMDB_LANGUAGE)
    configuration = json.loads((settings.TMDB_DATA_DIR / "configuration.json").read_text(encoding="utf-8"))
    with transaction.atomic():
        movie = Movie.objects.get(tmdb_id=item["tmdb_id"])
        ranks = {movie.tmdb_id: movie.catalog_rank}
        def related_counts():
            return {
                "movie": Movie.objects.filter(tmdb_id=movie.tmdb_id).count(),
                "genres": Genre.objects.filter(tmdb_id__in=[genre["id"] for genre in item["_genres"]]).count(),
                "people": Person.objects.filter(tmdb_id__in=[credit["id"] for credit in item["_credits"]]).count(),
                "credits": MovieCredit.objects.filter(movie=movie).count(),
            }
        upsert_movies([item], ranks)
        before = related_counts()
        upsert_movies([item], ranks)
        after = related_counts()
        assert before == after, "Repeat import duplicated catalog records or credits."
        movie.refresh_from_db()
        assert movie.source_tags == [Movie.Source.TMDB]
        assert not movie.is_technique_source
        user = get_user_model().objects.create(username="phase2-check-" + uuid.uuid4().hex)
        profile = get_or_create_profile(user)
        assert get_or_create_profile(user).pk == profile.pk
        Rating.objects.create(user=user, movie=movie, score=10)
        rejects(lambda: Rating.objects.create(user=user, movie=movie, score=9))
        rejects(lambda: Rating.objects.filter(user=user, movie=movie).update(score=11))
        rejects(lambda: Rating.objects.filter(user=user, movie=movie).update(score=0))
        WatchlistItem.objects.create(user=user, movie=movie)
        rejects(lambda: WatchlistItem.objects.create(user=user, movie=movie))
        with CaptureQueriesContext(connection) as queries:
            movies = list(movie_details_queryset()[:20])
            rendered = MovieDetailSerializer(movies, many=True, context={"tmdb_configuration": configuration}).data
        assert len(queries) == 3, f"Expected three prefetched queries, saw {len(queries)}."
        assert rendered and all(not result["is_technique_source"] for result in rendered)
        for result in rendered:
            assert result["vote_count"] >= settings.TMDB_MIN_VOTES
            assert result["poster_url"] is None or result["poster_url"].startswith("https://image.tmdb.org/")
            assert result["trailer_embed_url"] is None or result["trailer_embed_url"].startswith("https://www.youtube.com/embed/")
        assert trailer_embed_url("") is None
        assert trailer_embed_url("<script>") is None
        assert Movie(source_tags=[Movie.Source.LETTERBOXD]).is_technique_source
        assert not Movie(source_tags=[Movie.Source.TMDB]).is_technique_source
        client = Client(HTTP_HOST="localhost")
        with CaptureQueriesContext(connection) as api_queries:
            response = client.get(f"/api/v1/movies/{movie.tmdb_id}/")
        assert response.status_code == 200
        assert response.json()["tmdb_id"] == movie.tmdb_id
        assert "poster_url" in response.json() and "trailer_embed_url" in response.json()
        assert len(api_queries) == 3
        assert client.post(f"/api/v1/movies/{movie.tmdb_id}/", {}).status_code == 405
        assert client.get("/api/v1/movies/0/").status_code == 404
        transaction.set_rollback(True)
    print("PASS: repeat imports preserve counts; profiles are idempotent; rating range and uniqueness; watchlist uniqueness; provenance rules; three-query serialization; media URL handling.")
    print("Used authentic TMDB records. All verification writes rolled back.")
    print("PASS: real movie detail HTTP JSON, three queries, POST rejected, missing movie returns 404.")


if __name__ == "__main__":
    main()
