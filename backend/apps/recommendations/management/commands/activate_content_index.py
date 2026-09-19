from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.recommendations.services.content.contracts import ContentIndexError
from apps.recommendations.services.content.registry import activate


class Command(BaseCommand):
    help = "Validate a built content index and activate it atomically. No training or database writes."

    def add_arguments(self, parser):
        parser.add_argument("directory")

    def handle(self, *args, **options):
        try:
            manifest = activate(options["directory"], settings.CONTENT_INDEX_POINTER)
        except (ContentIndexError, OSError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Activated {manifest['engine']} for {manifest['movie_count']} movies."))
