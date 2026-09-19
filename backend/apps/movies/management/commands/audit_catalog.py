"""Reconcile a completed import manifest with the real catalog."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min, Max, Q

from apps.movies.models import Movie, MovieCredit, Person, Genre
from apps.movies.services.tmdb import write_json


class Command(BaseCommand):
    help = "Audit a TMDB import manifest against stored IDs, filters, ranks and source tags."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)

    def handle(self, *args, **options):
        path = options["manifest"]
        if not path.exists():
            raise CommandError("Import manifest does not exist.")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        selected = {item["id"] for item in manifest["selected"]}
        completed = set(manifest["completed"])
        excluded = {int(movie_id) for movie_id in manifest["excluded"]}
        movies = Movie.objects.filter(tmdb_id__in=selected)
        actual = set(movies.values_list("tmdb_id", flat=True))
        policy = manifest["policy"]
        invalid = movies.filter(
            Q(vote_count__lt=policy["min_votes"]) | Q(vote_average__lt=policy["min_rating"])
            | Q(release_date__isnull=True) | Q(release_date__gt=manifest["release_before"])
        ).count()
        wrong_sources = movies.exclude(source_tags__contains=[Movie.Source.TMDB]).count()
        expected_ranks = {item["id"]: rank for rank, item in enumerate(manifest["selected"], 1)}
        wrong_ranks = sum(rank != expected_ranks[movie_id] for movie_id, rank in movies.values_list("tmdb_id", "catalog_rank"))
        report = {
            "manifest": path.name,
            "finished": bool(manifest.get("finished_at")),
            "selected": len(selected), "completed": len(completed), "excluded": len(excluded),
            "stored_selected": len(actual), "missing_completed": sorted(completed - actual),
            "unaccounted_selected": sorted(selected - completed - excluded),
            "invalid_policy_records": invalid, "missing_tmdb_source_tag": wrong_sources,
            "incorrect_snapshot_ranks": wrong_ranks,
            "selected_catalog": movies.aggregate(
                count=Count("id"), min_rating=Min("vote_average"), max_rating=Max("vote_average"),
                min_votes=Min("vote_count"), posters=Count("id", filter=~Q(poster_path="")),
                trailers=Count("id", filter=~Q(trailer_key="")),
                technique_sources=Count("id", filter=Q(source_tags__overlap=[Movie.Source.LETTERBOXD, Movie.Source.TSPDT])),
            ),
            "database_totals": {"movies": Movie.objects.count(), "genres": Genre.objects.count(), "people": Person.objects.count(), "credits": MovieCredit.objects.count()},
        }
        for key in ("min_rating", "max_rating"):
            value = report["selected_catalog"][key]
            report["selected_catalog"][key] = str(value) if value is not None else None
        write_json(settings.TMDB_DATA_DIR / "verification" / "catalog-audit.json", report)
        self.stdout.write(json.dumps(report, indent=2))
        if not report["finished"] or report["missing_completed"] or report["unaccounted_selected"] or invalid or wrong_sources or wrong_ranks:
            raise CommandError("Catalog audit found incomplete or inconsistent records.")
