from datetime import datetime, timezone
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.movies.models import Movie
from apps.recommendations.services.collaborative.artifacts import canonical_json, write_json


class Command(BaseCommand):
    help = "Export catalog identity data for exact MovieLens/TMDB mapping; no user data."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, default=settings.BASE_DIR.parent / "data/collaborative/catalog.json")

    def handle(self, *args, **options):
        movies = list(Movie.objects.order_by("tmdb_id").values("tmdb_id", "imdb_id", "title"))
        if not movies:
            raise CommandError("The TMDB catalog is empty.")
        checksum = hashlib.sha256(canonical_json(movies).encode("utf-8")).hexdigest()
        write_json(options["output"], {"schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "catalog_sha256": checksum, "movies": movies})
        self.stdout.write(f"Exported {len(movies)} catalog identities. SHA-256: {checksum}")
