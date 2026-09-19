"""Check image delivery and YouTube embed metadata without downloading trailers."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import requests

from apps.movies.models import Movie
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.queries import movie_details_queryset
from apps.movies.services.tmdb import write_json


class Command(BaseCommand):
    help = "Verify a stored film's poster response and YouTube oEmbed metadata; no trailer downloads."

    def add_arguments(self, parser):
        parser.add_argument("tmdb_id", type=int)

    def handle(self, *args, **options):
        try:
            movie = movie_details_queryset().get(tmdb_id=options["tmdb_id"])
        except Movie.DoesNotExist:
            raise CommandError("Movie is not in the catalog.") from None
        path = settings.TMDB_DATA_DIR / "configuration.json"
        if not path.exists():
            raise CommandError("Import the TMDB configuration before checking media.")
        config = json.loads(path.read_text(encoding="utf-8"))
        payload = dict(MovieDetailSerializer(movie, context={"tmdb_configuration": config}).data)
        report = {"tmdb_id": movie.tmdb_id, "title": movie.title}
        try:
            if payload["poster_url"]:
                with requests.get(payload["poster_url"], stream=True, timeout=(10, 20)) as response:
                    report["poster_http_status"] = response.status_code
                    report["poster_content_type"] = response.headers.get("Content-Type", "")
                    report["poster_verified"] = response.status_code == 200 and report["poster_content_type"].startswith("image/")
            else:
                report["poster_verified"] = False
                report["poster_note"] = "TMDB supplies no poster."
            if payload["trailer_embed_url"]:
                response = requests.get("https://www.youtube.com/oembed", params={
                    "url": f"https://www.youtube.com/watch?v={movie.trailer_key}", "format": "json",
                }, timeout=(10, 20))
                report["youtube_oembed_http_status"] = response.status_code
                embed = response.json() if response.status_code == 200 else {}
                report["trailer_embed_verified"] = embed.get("type") == "video" and "<iframe" in embed.get("html", "")
            else:
                report["trailer_embed_verified"] = False
                report["trailer_note"] = "TMDB supplies no eligible YouTube trailer."
        except (requests.RequestException, ValueError):
            raise CommandError("Media verification network request failed; retry when the media provider is reachable.") from None
        write_json(settings.TMDB_DATA_DIR / "verification" / f"movie-{movie.tmdb_id}.json", payload)
        write_json(settings.TMDB_DATA_DIR / "verification" / f"media-{movie.tmdb_id}.json", report)
        self.stdout.write(json.dumps(report, indent=2))
        if not report.get("poster_verified") or not report.get("trailer_embed_verified"):
            raise CommandError("Media is absent or the provider did not confirm it; see the verification report.")
