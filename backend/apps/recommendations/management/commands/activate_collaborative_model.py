from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.recommendations.services.collaborative.contracts import CollaborativeModelError
from apps.recommendations.services.collaborative.registry import activate


class Command(BaseCommand):
    help = "Verify and atomically activate a trained collaborative model."

    def add_arguments(self, parser):
        parser.add_argument("directory")

    def handle(self, *args, **options):
        try:
            manifest = activate(options["directory"], settings.COLLABORATIVE_MODEL_POINTER)
        except (CollaborativeModelError, OSError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Activated {manifest['engine']} for {manifest['movie_count']} catalog movies.")
