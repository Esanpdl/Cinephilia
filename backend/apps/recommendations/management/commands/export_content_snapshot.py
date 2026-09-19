import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.recommendations.services.content.snapshot import export_snapshot


class Command(BaseCommand):
    help = "Export authentic catalog metadata for the Lightning content-index build."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, default=settings.BASE_DIR.parent / "data" / "content" / "catalog.json")

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(export_snapshot(options["output"]), indent=2))
