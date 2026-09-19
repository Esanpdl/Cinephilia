"""Validate, pre-dedupe, resolve, review, and merge the user's scraped lists."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from apps.movies.services.tmdb import TMDBClient, TMDBError, write_json
from apps.cinematography.services.source_lists import SOURCES, SourceError, load_source, deduplicate, validate_unique_source_matches
from apps.cinematography.services.resolution import Resolver, read_overrides, manual_result
from apps.cinematography.services.ingestion import apply_plan


class Command(BaseCommand):
    help = "Resolve authentic scraped list identities. Default: report only; --apply merges a fully resolved plan."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, default=settings.BASE_DIR.parent / "data/raw/technique_sources")
        parser.add_argument("--decisions", type=Path)
        parser.add_argument("--allow-incomplete", action="store_true")
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, help="Resolve only this many pending groups for inspection; cannot combine with --apply.")
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--retry-review", action="store_true", help="Retry unresolved matches using the current resolver.")

    def handle(self, *args, **options):
        client = None
        try:
            if not 1 <= options["workers"] <= 8 or options["limit"] is not None and options["limit"] < 1:
                raise SourceError("Use workers 1–8 and a positive limit.")
            if options["apply"] and (options["limit"] or options["validate_only"]):
                raise SourceError("--apply cannot be combined with --limit or --validate-only.")
            sources = [load_source(options["source_dir"] / f"{source}.json", options["allow_incomplete"]) for source in SOURCES]
            if len({source.source for source in sources}) != 2:
                raise SourceError("Supply exactly one file for each supported source.")
            entries = [entry for source in sources for entry in source.entries]
            groups = deduplicate(entries)
            input_hashes = {source.source: source.digest for source in sources}
            run_id = hashlib.sha256(json.dumps(input_hashes, sort_keys=True).encode()).hexdigest()[:20]
            directory = settings.BASE_DIR.parent / "data/phase7" / run_id
            directory.mkdir(parents=True, exist_ok=True)
            validation = {"input_hashes": input_hashes, "entries": len(entries), "groups_before_tmdb": len(groups), "merged_before_tmdb": len(entries) - len(groups)}
            write_json(directory / "validation.json", validation)
            write_json(directory / "merged.json", {
                "input_hashes": input_hashes, "unique_groups": len(groups),
                "movies": [{"title": group[0]["match_title"], "citations": group} for group in groups],
            })
            self.stdout.write(f"Validated {len(entries)} entries; {len(groups)} groups after conservative cross-source deduplication.")
            self.stdout.write(f"Evidence directory: {directory}")
            if options["validate_only"]:
                return
            decisions = read_overrides(options["decisions"], input_hashes, {entry["key"] for entry in entries})
            client = TMDBClient()
            resolver = Resolver(client, directory)
            connection.close()  # No idle pool slot while TMDB work runs.
            plan_path = directory / "plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {"input_hashes": input_hashes, "results": {}}
            if plan.get("input_hashes") != input_hashes:
                raise SourceError("Saved plan input hashes do not match these sources.")
            results = plan["results"]
            # Overrides are individual, so a reviewed split does not inherit a
            # provisional pair's identity. Remaining members resolve separately.
            remaining_groups = []
            for group in groups:
                for entry in group:
                    if entry["key"] in decisions:
                        results[entry["key"]] = manual_result(decisions[entry["key"]], resolver)
                members = [entry for entry in group if entry["key"] not in decisions]
                if not members:
                    continue
                if options["retry_review"] and any(results.get(entry["key"], {}).get("status") in {"review", "error"} for entry in members):
                    for entry in members:
                        results.pop(entry["key"], None)
                if any(entry["key"] not in results for entry in members):
                    remaining_groups.append(members)
            if options["limit"]:
                remaining_groups = remaining_groups[:options["limit"]]
            with ThreadPoolExecutor(max_workers=options["workers"]) as pool:
                futures = {pool.submit(resolver.resolve, members): members for members in remaining_groups}
                for index, future in enumerate(as_completed(futures), 1):
                    members = futures[future]
                    try:
                        result = future.result()
                    except TMDBError as error:
                        result = {"status": "error", "tmdb_id": None, "reason": str(error)}
                        self.stderr.write(f"TMDB error for {members[0]['key']}: {error}")
                    for entry in members:
                        results[entry["key"]] = dict(result, grouped_keys=[member["key"] for member in members])
                    write_json(plan_path, plan)
                    if index % 25 == 0 or index == len(futures):
                        self.stdout.write(f"Resolved {index}/{len(futures)} pending groups; saved {len(results)}/{len(entries)} source entries.")
                        self.stdout.flush()
            write_json(plan_path, plan)
            validate_unique_source_matches(entries, results)
            review = [dict(entry, resolution=results.get(entry["key"], {"status": "pending"})) for entry in entries if results.get(entry["key"], {}).get("status") not in {"resolved", "excluded", "unmatched"}]
            write_json(directory / "review.json", {"input_hashes": input_hashes, "entries": review})
            write_json(directory / "decisions-template.json", {"input_hashes": input_hashes, "decisions": {}})
            report = {
                **validation, "resolved_entries": sum(result["status"] == "resolved" for result in results.values()),
                "excluded_entries": sum(result["status"] == "excluded" for result in results.values()),
                "unmatched_entries": sum(result["status"] == "unmatched" for result in results.values()),
                "review_or_pending_entries": len(review),
                "distinct_resolved_movies": len({result["tmdb_id"] for result in results.values() if result["status"] == "resolved"}),
                "reported_at": timezone.now().isoformat(), "applied": False,
            }
            write_json(directory / "report.json", report)
            resolved_movies = {}
            for entry in entries:
                result = results.get(entry["key"], {})
                if result.get("status") == "resolved":
                    movie_id = result["tmdb_id"]
                    record = resolved_movies.setdefault(movie_id, {"tmdb_id": movie_id, "citations": []})
                    record["citations"].append(entry)
            write_json(directory / "enriched_movies.json", {
                "input_hashes": input_hashes,
                "movies": [dict(record, tmdb=resolver.detail(movie_id)) for movie_id, record in sorted(resolved_movies.items())],
            })
            if options["apply"]:
                if review:
                    raise SourceError(f"{len(review)} entries need review. See {directory / 'review.json'}; database unchanged.")
                # Hydrate/validate all evidence before opening the atomic DB transaction.
                for result in results.values():
                    if result["status"] == "resolved":
                        resolver.detail(result["tmdb_id"])
                report["database"] = apply_plan(sources, entries, results, resolver, progress=self.stdout.write)
                report["applied"] = True
                write_json(directory / "report.json", report)
            self.stdout.write(json.dumps(report, indent=2))
        except (SourceError, TMDBError, OSError, ValueError) as error:
            raise CommandError(str(error)) from None
        finally:
            if client:
                client.close()
            connection.close()
