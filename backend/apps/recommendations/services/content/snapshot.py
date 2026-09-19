"""Export a consistent catalog snapshot in three bulk reads; never export user data."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from django.db import connection, transaction

from apps.movies.models import Movie, MovieCredit
from .artifacts import canonical_json, write_json


def export_snapshot(destination):
    # Repeatable read keeps movie and relation queries on one database snapshot.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        records = list(Movie.objects.order_by("tmdb_id").values(
            "id", "tmdb_id", "title", "release_date", "overview", "keywords",
        ))
        if not records:
            raise ValueError("The movie catalog is empty. Complete the TMDB import first.")
        genres = defaultdict(list)
        for link in Movie.genres.through.objects.order_by("movie_id", "genre__tmdb_id").values(
            "movie_id", "genre__tmdb_id", "genre__name",
        ).iterator(chunk_size=5000):
            genres[link["movie_id"]].append({"id": link["genre__tmdb_id"], "name": link["genre__name"]})
        credits = defaultdict(lambda: {"cast": [], "directors": []})
        for credit in MovieCredit.objects.order_by("movie_id", "cast_order", "person__tmdb_id").values(
            "movie_id", "role", "cast_order", "person__tmdb_id", "person__name",
        ).iterator(chunk_size=10000):
            field = "cast" if credit["role"] == MovieCredit.Role.CAST else "directors"
            credits[credit["movie_id"]][field].append({
                "id": credit["person__tmdb_id"], "name": credit["person__name"], "order": credit["cast_order"],
            })
    movies = []
    for row in records:
        movie_id = row.pop("id")
        row["release_date"] = row["release_date"].isoformat() if row["release_date"] else None
        row["genres"] = genres[movie_id]
        row.update(credits[movie_id])
        movies.append(row)
    fingerprint = hashlib.sha256(canonical_json(movies).encode("utf-8")).hexdigest()
    payload = {"schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "catalog_sha256": fingerprint, "movies": movies}
    destination = Path(destination)
    write_json(destination, payload)
    return {"movie_count": len(movies), "catalog_sha256": fingerprint, "path": str(destination)}
