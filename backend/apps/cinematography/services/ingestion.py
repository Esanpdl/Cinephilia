"""Apply only fully resolved evidence, preserving catalog identities and provenance."""
from datetime import datetime
from django.db import connection, transaction

from apps.movies.models import Movie
from apps.movies.services.catalog import normalize_details, upsert_movies
from .source_lists import SourceError, validate_unique_source_matches
from ..models import TechniqueSourceSnapshot, TechniqueSourceCitation


@transaction.atomic
def apply_plan(sources, entries, results, resolver, progress=None):
    expected_entries = [entry for source in sources for entry in source.entries]
    if entries != expected_entries or set(results) != {entry["key"] for entry in entries}:
        raise SourceError("Plan must cover exactly the supplied source entries.")
    validate_unique_source_matches(entries, results)
    # Same lock as import_tmdb: source tags and catalog upserts cannot race.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(174839201)")
        if not cursor.fetchone()[0]:
            raise SourceError("Another catalog import is running; retry later.")
    if any(results[entry["key"]]["status"] not in {"resolved", "excluded", "unmatched"} for entry in entries):
        raise SourceError("Unresolved source entries remain. Review them before applying.")
    for result in results.values():
        movie_id = result.get("tmdb_id")
        if result["status"] == "resolved" and (type(movie_id) is not int or movie_id <= 0) or result["status"] in {"excluded", "unmatched"} and movie_id is not None:
            raise SourceError("A plan contains an invalid resolved or excluded identity.")
    movie_ids = sorted({result["tmdb_id"] for result in results.values() if result["status"] == "resolved"})
    existing = dict(Movie.objects.filter(tmdb_id__in=movie_ids).values_list("tmdb_id", "catalog_rank"))
    # Refresh full TMDB details for every matched movie, while preserving the
    # original catalog ranks, primary keys, ratings, and watchlists.
    new_ids = [movie_id for movie_id in movie_ids if movie_id not in existing]
    for offset in range(0, len(movie_ids), 100):
        batch = movie_ids[offset:offset + 100]
        upsert_movies([normalize_details(resolver.detail(movie_id), resolver.client.language) for movie_id in batch], {movie_id: existing.get(movie_id) for movie_id in batch})
        if progress:
            progress(f"Updated full metadata for {min(offset + 100, len(movie_ids))}/{len(movie_ids)} movies; transaction remains uncommitted.")
    movies = Movie.objects.in_bulk(movie_ids, field_name="tmdb_id")
    source_snapshots = {}
    created_snapshots = 0
    for source in sources:
        snapshot, created = TechniqueSourceSnapshot.objects.get_or_create(
            source=source.source, sha256=source.digest,
            defaults={
                "source_list_url": source.payload["source_list_url"],
                "retrieved_at": datetime.fromisoformat(source.payload["retrieved_at"].replace("Z", "+00:00")),
                "actual_count": source.payload["actual_count"], "complete": source.payload["complete"],
                "raw_payload": source.payload,
            },
        )
        created_snapshots += created
        source_snapshots[source.source] = snapshot
    citations = []
    for entry in entries:
        result = results[entry["key"]]
        movie = movies.get(result["tmdb_id"])
        snapshot = source_snapshots[entry["source"]]
        citations.append(TechniqueSourceCitation(
            snapshot=snapshot, rank=entry["rank"], source_title=entry["title"],
            source_year=entry["year"], source_director=entry["director"] or "",
            source_page_url=entry["source_page_url"], source_item_url=entry["source_item_url"] or "",
            movie=movie, status=result["status"], match_evidence=result,
        ))
    old = {(citation.snapshot_id, citation.rank): citation for citation in TechniqueSourceCitation.objects.filter(snapshot__in=source_snapshots.values())}
    pending = []
    for citation in citations:
        previous = old.get((citation.snapshot_id, citation.rank))
        if previous:
            if previous.movie_id != citation.movie_id or previous.status != citation.status:
                raise SourceError("An imported immutable source snapshot has a different identity mapping. Investigate the correction explicitly.")
        else:
            pending.append(citation)
    TechniqueSourceCitation.objects.bulk_create(pending, batch_size=500)
    memberships = {}
    for movie_pk, source_name in TechniqueSourceCitation.objects.filter(movie__tmdb_id__in=movie_ids, status="resolved").values_list("movie_id", "snapshot__source").distinct():
        memberships.setdefault(movie_pk, set()).add(source_name)
    changed = []
    for movie in movies.values():
        tags = sorted(set(movie.source_tags) | memberships.get(movie.pk, set()))
        if movie.source_tags != tags:
            movie.source_tags = tags
            changed.append(movie)
    Movie.objects.bulk_update(changed, ["source_tags"], batch_size=500)
    return {
        "source_entries": len(entries), "distinct_movies": len(movie_ids),
        "new_movies": len(new_ids), "existing_movies": len(existing),
        "new_snapshots": created_snapshots, "new_citations": len(pending),
        "flagged_movies_updated": len(changed),
        "excluded_entries": sum(result["status"] == "excluded" for result in results.values()),
        "unmatched_entries": sum(result["status"] == "unmatched" for result in results.values()),
        "missing_posters": sum(not movie.poster_path for movie in movies.values()),
        "missing_trailers": sum(not movie.trailer_key for movie in movies.values()),
    }
