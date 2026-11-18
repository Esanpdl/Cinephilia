"""Capture TMDB's ranked eligible catalog and hydrate it in resumable batches."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from math import ceil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.db import connection, reset_queries
from django.utils import timezone

from apps.movies.models import Movie
from apps.movies.services.catalog import normalize_details, upsert_movies
from apps.movies.services.tmdb import TMDBClient, TMDBError, write_json


class Command(BaseCommand):
    help = "Import up to 10,000 highest-rated eligible TMDB films; rerun the same options to resume."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10000)
        parser.add_argument("--min-votes", type=int, default=settings.TMDB_MIN_VOTES)
        parser.add_argument("--min-rating", type=float, default=settings.TMDB_MIN_RATING)
        parser.add_argument("--workers", type=int, default=8)
        parser.add_argument("--batch-size", type=int, default=250)
        parser.add_argument("--new-snapshot", action="store_true", help="Capture a new ranking and refresh selected movies; retains existing catalog rows.")

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 10000 or options["min_votes"] < 1 or not 0 <= options["min_rating"] <= 10:
            raise CommandError("Use limit 1–10000, min-votes >=1 and min-rating 0–10.")
        if not 1 <= options["workers"] <= 8 or not 1 <= options["batch_size"] <= 500:
            raise CommandError("Use workers 1–8 and batch-size 1–500.")
        client = None
        locked = False
        try:
            # Session pooling preserves this lock across transactions; no concurrent import races.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(174839201)")
                locked = cursor.fetchone()[0]
            if not locked:
                raise CommandError("Another TMDB catalog import is running.")
            client = TMDBClient()
            self.run_import(client, options)
        except TMDBError as error:
            raise CommandError(str(error)) from None
        finally:
            if client:
                client.close()
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(174839201)")

    def run_import(self, client, options):
        policy = {key: options[key] for key in ("limit", "min_votes", "min_rating")}
        policy["language"] = client.language
        fingerprint = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:16]
        manifest_path = settings.TMDB_DATA_DIR / "imports" / f"catalog-{fingerprint}.json"
        if manifest_path.exists() and not options["new_snapshot"]:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["policy"] != policy:
                raise CommandError("Import manifest policy differs; use --new-snapshot.")
            self.stdout.write(f"Resuming saved catalog selection: {manifest_path.name}")
        else:
            if manifest_path.exists():
                archive = manifest_path.with_name(manifest_path.stem + f"-{timezone.now():%Y%m%d%H%M%S}.json")
                manifest_path.replace(archive)
            manifest = {
                "policy": policy, "started_at": timezone.now().isoformat(),
                "release_before": date.today().isoformat(), "next_page": 1,
                "selected": [], "completed": [], "excluded": {}, "selection_complete": False,
            }
        seen = {item["id"] for item in manifest["selected"]}
        while not manifest["selection_complete"]:
            page = manifest["next_page"]
            response = client.discover(page, options["min_votes"], options["min_rating"], manifest["release_before"], refresh=options["new_snapshot"])
            if response.get("page") != page or not isinstance(response.get("results"), list) or not isinstance(response.get("total_pages"), int) or not isinstance(response.get("total_results"), int):
                raise TMDBError("Unexpected TMDB discovery response; cannot verify catalog selection.")
            manifest["total_eligible_reported"] = response["total_results"]
            max_pages = min(500, response["total_pages"], ceil(options["limit"] / 20))
            for item in response["results"]:
                try:
                    movie_id = item["id"]
                    if not isinstance(movie_id, int) or movie_id <= 0:
                        raise ValueError
                    if item["vote_count"] < options["min_votes"] or item["vote_average"] < options["min_rating"]:
                        raise ValueError
                    if not item["title"]:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    raise TMDBError("A discovery result violates the requested voting filters or lacks its identity.") from None
                if movie_id not in seen and len(manifest["selected"]) < options["limit"]:
                    manifest["selected"].append({"id": movie_id, "title": item["title"], "vote_average": item["vote_average"], "vote_count": item["vote_count"]})
                    seen.add(movie_id)
            manifest["next_page"] = page + 1
            manifest["selection_complete"] = page >= max_pages or len(manifest["selected"]) >= options["limit"] or not response["results"]
            write_json(manifest_path, manifest)
            self.stdout.write(f"Selection page {page}/{max_pages}: {len(manifest['selected'])} unique films", ending="\n")
            self.stdout.flush()
        if not manifest["selected"]:
            raise CommandError("TMDB returned no films matching these filters. No substitute films were imported.")
        # Discovery is a changing live feed, not an atomic snapshot. Normalize the
        # captured scores and break ties deterministically without inventing scores.
        manifest["selected"].sort(key=lambda item: (-item["vote_average"], -item["vote_count"], item["id"]))
        write_json(manifest_path, manifest)
        self.stdout.write(f"Selected {len(manifest['selected'])} films; TMDB reports {manifest['total_eligible_reported']} eligible. The API permits at most 500 pages / 10,000 results.")
        self.stdout.write("Top 10 in the captured TMDB ranking:")
        for rank, item in enumerate(manifest["selected"][:10], 1):
            self.stdout.write(f"{rank}. {item['title']} — {item['vote_average']}/10 ({item['vote_count']} votes), TMDB {item['id']}")
        configuration = client.configuration()
        write_json(settings.TMDB_DATA_DIR / "configuration.json", configuration)
        ranks = {item["id"]: rank for rank, item in enumerate(manifest["selected"], 1)}
        completed = set(manifest["completed"])
        # Recover if database records were removed after an earlier successful run.
        existing = set(Movie.objects.filter(tmdb_id__in=completed).values_list("tmdb_id", flat=True))
        completed &= existing
        pending = [item["id"] for item in manifest["selected"] if item["id"] not in completed and str(item["id"]) not in manifest["excluded"]]
        with ThreadPoolExecutor(max_workers=options["workers"]) as pool:
            def fetch_batch(batch):
                return [pool.submit(client.details, movie_id, refresh=options["new_snapshot"]) for movie_id in batch]

            batches = iter(pending[offset:offset + options["batch_size"]] for offset in range(0, len(pending), options["batch_size"]))
            batch = next(batches, [])
            futures = fetch_batch(batch)
            while batch:
                details = [future.result() for future in futures]
                # Keep only one upcoming batch in memory and overlap network work
                # with this batch's database transaction, using the same rate gate.
                next_batch = next(batches, [])
                next_futures = fetch_batch(next_batch)
                normalized = []
                for movie_id, payload in zip(batch, details):
                    item = normalize_details(payload, client.language)
                    if item["tmdb_id"] != movie_id:
                        raise TMDBError("TMDB detail identity does not match the requested movie.")
                    if item["vote_count"] < options["min_votes"] or item["vote_average"] < options["min_rating"] or item["_adult"] or item["_video"] or not item["release_date"] or item["release_date"].isoformat() > manifest["release_before"]:
                        manifest["excluded"][str(movie_id)] = "Details no longer meet the captured discovery filters."
                    else:
                        normalized.append(item)
                if normalized:
                    upsert_movies(normalized, ranks)
                    completed.update(item["tmdb_id"] for item in normalized)
                manifest["completed"] = sorted(completed)
                manifest["updated_at"] = timezone.now().isoformat()
                write_json(manifest_path, manifest)
                self.stdout.write(f"Stored {len(completed)}/{len(ranks)} films; excluded {len(manifest['excluded'])}. Checkpoint saved.")
                self.stdout.flush()
                reset_queries()  # Avoid retaining every bulk SQL statement in DEBUG mode.
                batch, futures = next_batch, next_futures
        manifest["finished_at"] = timezone.now().isoformat()
        write_json(manifest_path, manifest)
        cache.clear()
        self.stdout.write(self.style.SUCCESS(f"Import finished: {len(completed)} hydrated movies. Manifest: {manifest_path}"))
