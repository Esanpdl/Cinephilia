"""Verify imported real source lists and catalog invariants without writing film data."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from apps.movies.models import Movie
from apps.ratings.models import Rating, WatchlistItem
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.queries import movie_details_queryset
from apps.movies.services.presentation import media_context
from apps.movies.services.tmdb import write_json
from apps.cinematography.models import TechniqueSourceCitation, TechniqueSourceSnapshot
from apps.cinematography.services.source_lists import SOURCES, load_source

sources = [load_source(ROOT / "data/raw/technique_sources" / f"{source}.json") for source in SOURCES]
hashes = {source.source: source.digest for source in sources}
run_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:20]
directory = ROOT / "data/phase7" / run_id
baseline = json.loads((ROOT / "data/phase7/baseline.json").read_text(encoding="utf-8"))
plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
report = {}
try:
    movie_ids = {result["tmdb_id"] for result in plan["results"].values() if result["status"] == "resolved"}
    assert len(plan["results"]) == sum(len(source.entries) for source in sources)
    for source in sources:
        snapshot = TechniqueSourceSnapshot.objects.get(source=source.source, sha256=source.digest)
        assert snapshot.raw_payload == source.payload
        citations = {entry.rank: entry for entry in snapshot.citations.select_related("movie")}
        assert len(citations) == source.payload["actual_count"]
        for entry in source.entries:
            citation = citations[entry["rank"]]
            result = plan["results"][entry["key"]]
            assert citation.source_title == entry["title"]
            assert citation.source_year == entry["year"]
            assert citation.source_director == (entry["director"] or "")
            assert citation.source_page_url == entry["source_page_url"]
            assert citation.source_item_url == (entry["source_item_url"] or "")
            assert citation.status == result["status"]
            assert (citation.movie.tmdb_id if citation.movie_id else None) == result["tmdb_id"]
        report[source.source] = {"citations": len(citations), "raw_snapshot_preserved": True}
    catalog = {row[0]: row[1:] for row in Movie.objects.values_list("tmdb_id", "pk", "catalog_rank")}
    assert all(list(catalog[movie_id]) == [pk, rank] for movie_id, pk, rank in baseline["catalog"])
    expected_new = movie_ids - {row[0] for row in baseline["catalog"]}
    assert len(catalog) == baseline["movies"] + len(expected_new)
    flagged_ids = set(Movie.objects.filter(source_tags__overlap=list(SOURCES)).values_list("tmdb_id", flat=True))
    cited_ids = set(TechniqueSourceCitation.objects.filter(status="resolved").values_list("movie__tmdb_id", flat=True))
    assert flagged_ids == cited_ids
    assert movie_ids <= flagged_ids
    assert get_user_model().objects.count() == baseline["users"]
    assert Rating.objects.count() == baseline["ratings"]
    assert WatchlistItem.objects.count() == baseline["watchlist"]
    for name, expected_hash in baseline["model_pointers"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_hash
    # Same existing API serializer used by the live site; three data queries,
    # independent of how many citations a movie carries.
    selected = list(movie_ids)[:3] + sorted(expected_new)[:3]
    with CaptureQueriesContext(connection) as captured:
        movies = list(movie_details_queryset().filter(tmdb_id__in=selected))
        serialized = MovieDetailSerializer(movies, many=True, context=media_context()).data
    assert len(captured) == 3
    assert all(item["is_technique_source"] for item in serialized)
    assert all(item["poster_url"] is None or item["poster_url"].startswith("https://image.tmdb.org/") for item in serialized)
    assert all(item["trailer_embed_url"] is None or item["trailer_embed_url"].startswith("https://www.youtube.com/embed/") for item in serialized)
    report.update({
        "passed": True, "catalog_movies": len(catalog), "new_movies": len(expected_new),
        "resolved_source_movies": len(movie_ids), "flagged_equals_cited": True,
        "original_ids_and_ranks_preserved": True, "user_data_unchanged": True,
        "trained_model_pointers_unchanged": True, "detail_queries": len(captured),
        "sample_new_tmdb_ids": sorted(expected_new)[:3],
    })
    write_json(directory / "verification.json", report)
    print(json.dumps(report, indent=2))
finally:
    connection.close()

