import logging
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cinematography.models import TechniqueSourceCitation
from apps.movies.models import Movie

logger = logging.getLogger(__name__)

TARGET_TMDB_ID = 980431


class Command(BaseCommand):
    help = "Fully remove Avatar Aang: The Last Airbender (TMDB 980431) from the database."

    def handle(self, *args, **options):
        try:
            movie = Movie.objects.get(tmdb_id=TARGET_TMDB_ID)
        except Movie.DoesNotExist:
            self.stdout.write(self.style.SUCCESS(f"Movie TMDB {TARGET_TMDB_ID} is already absent from the database."))
            return

        with transaction.atomic():
            citations = TechniqueSourceCitation.objects.filter(movie=movie)
            citation_count = citations.count()
            for citation in citations:
                citation.status = TechniqueSourceCitation.Status.EXCLUDED
                citation.movie = None
                citation.save(update_fields=["status", "movie"])

            movie_title = movie.title
            movie.delete()
            cache.clear()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully removed '{movie_title}' (TMDB {TARGET_TMDB_ID}) from database and updated {citation_count} citation(s)."
            )
        )
