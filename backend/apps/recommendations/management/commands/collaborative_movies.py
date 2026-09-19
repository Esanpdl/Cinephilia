import json

from django.core.management.base import BaseCommand, CommandError

from apps.recommendations.services.collaborative.contracts import CollaborativeModelError
from apps.recommendations.services.collaborative.registry import get_collaborative_service, history_for_user


class Command(BaseCommand):
    help = "Inspect internal collaborative recommendations with real site ratings or the authentic MovieLens demo."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--user-id", type=int, help="A Django user ID; reads only that account's site ratings.")
        group.add_argument("--demo", action="store_true", help="Use the public MovieLens history saved with evaluation evidence.")
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        try:
            service = get_collaborative_service()
            if options["demo"]:
                evidence = json.loads((service.directory / "evaluation.json").read_text(encoding="utf-8"))["authentic_demo_profile"]
                history = {entry["tmdb_id"]: entry["score"] for entry in evidence["ratings"]}
                source = {"dataset": evidence["source"], "movielens_user_id": evidence["movielens_user_id"]}
            else:
                history = history_for_user(options["user_id"])
                source = {"django_user_id": options["user_id"]}
            matches = service.recommend(history, options["limit"])
            result = {"source": source, "profile": service.profile_status(history), "results": [{"tmdb_id": score.tmdb_id, "title": service.movie(score.tmdb_id)["title"], "predicted_rating": round(score.predicted_rating, 4), "normalized_score": round(score.normalized_score, 6)} for score in matches]}
        except (CollaborativeModelError, OSError, ValueError, KeyError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(result, indent=2))
