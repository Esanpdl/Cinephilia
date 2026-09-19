import json

from django.core.management.base import BaseCommand, CommandError

from apps.recommendations.services.content.contracts import ContentIndexError
from apps.recommendations.services.content.registry import get_content_service


class Command(BaseCommand):
    help = "Inspect internal content similarity without database or TMDB requests."

    def add_arguments(self, parser):
        parser.add_argument("tmdb_id", type=int)
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--exclude", type=int, nargs="*", default=[])
        parser.add_argument("--explain", action="store_true")

    def handle(self, *args, **options):
        try:
            service = get_content_service()
            matches = service.similar(options["tmdb_id"], options["limit"], options["exclude"])
            result = {
                "query": service.movie(options["tmdb_id"])["title"],
                "catalog_sha256": service.manifest["catalog_sha256"],
                "results": [{
                    "tmdb_id": match.tmdb_id, "title": service.movie(match.tmdb_id)["title"],
                    "score": round(match.score, 6),
                    **({"explanation": service.explain(options["tmdb_id"], match.tmdb_id)} if options["explain"] else {}),
                } for match in matches],
            }
        except (ContentIndexError, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
