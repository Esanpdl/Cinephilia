import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.movies.models import Movie
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.queries import movie_details_queryset


class Command(BaseCommand):
    help = "Print a stored movie's REST-ready JSON, including embeddable poster and YouTube URLs."

    def add_arguments(self, parser):
        parser.add_argument("tmdb_id", type=int)

    def handle(self, *args, **options):
        try:
            movie = movie_details_queryset().get(tmdb_id=options["tmdb_id"])
        except Movie.DoesNotExist:
            raise CommandError("Movie is not in the imported catalog.") from None
        configuration_path = settings.TMDB_DATA_DIR / "configuration.json"
        if not configuration_path.exists():
            raise CommandError("Run import_tmdb to fetch the authentic TMDB image configuration first.")
        configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
        payload = MovieDetailSerializer(movie, context={"tmdb_configuration": configuration}).data
        self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
