"""Read-only audit of catalog provenance, deduplication and the 500-film handoff."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection
from django.db.models import Count
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from apps.movies.models import Movie
from apps.movies.views import MovieListView
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.tmdb import write_json
from apps.cinematography.models import TechniqueSourceCitation, TechniqueSourceSnapshot
from apps.cinematography.services.source_lists import ALL_SOURCES, SOURCE_COUNTS, load_source
from apps.recommendations.services.content.registry import get_content_service


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main():
    report = {"sources": {}, "collections": {}, "homepage": {}}
    movies = {movie.tmdb_id: movie for movie in Movie.objects.all()}
    assert len(movies) == Movie.objects.count() == 11066
    assert not Movie.objects.values("tmdb_id").annotate(n=Count("id")).filter(n__gt=1).exists()
    baseline = read("data/phase7/baseline.json")
    for mid, pk, rank in baseline["catalog"]:
        assert (movies[mid].pk, movies[mid].catalog_rank) == (pk, rank)
    source_ids = set()
    memberships = {}
    for source in ALL_SOURCES:
        raw = load_source(ROOT / "data/raw/technique_sources" / (source + ".json"))
        snapshot = TechniqueSourceSnapshot.objects.get(source=source, sha256=raw.digest)
        assert snapshot.raw_payload == raw.payload
        citations = list(snapshot.citations.select_related("movie"))
        assert len(citations) == SOURCE_COUNTS[source]
        assert {c.rank for c in citations} == set(range(1, len(citations) + 1))
        entries = {entry["rank"]: entry for entry in raw.entries}
        resolved = []
        for citation in citations:
            entry = entries[citation.rank]
            assert (citation.source_title, citation.source_year, citation.source_director) == (entry["title"], entry["year"], entry["director"] or "")
            assert citation.source_page_url == entry["source_page_url"]
            assert citation.source_item_url == (entry["source_item_url"] or "")
            if citation.status == "resolved":
                mid = citation.movie.tmdb_id
                assert source in movies[mid].source_tags
                source_ids.add(mid)
                resolved.append(mid)
                memberships.setdefault(mid, {})[source] = citation.rank
            else:
                assert citation.movie_id is None
        assert len(resolved) == len(set(resolved))
        assert set(resolved) == {mid for mid, movie in movies.items() if source in movie.source_tags}
        report["sources"][source] = {"citations": len(citations), "resolved": len(resolved), "snapshot_sha256": raw.digest}
    assert source_ids == {mid for mid, movie in movies.items() if movie.is_technique_source}
    curation = read("data/expansion/curation.json")
    assert len(curation["people"]) == 25 and len(curation["collections"]) == 29
    curated_ids = set()
    for tag, ids in curation["collections"].items():
        assert len(ids) == len(set(ids))
        assert set(ids) == {mid for mid, movie in movies.items() if tag in movie.curation_tags}
        if tag.startswith("director:"):
            director_id = int(tag.split(":")[1])
            verified = set(Movie.objects.filter(credits__role="director", credits__person__tmdb_id=director_id).values_list("tmdb_id", flat=True))
            assert set(ids) <= verified
        for mid in ids:
            payload = read(f"data/expansion/curated/details/{mid}.json")
            assert movies[mid].title == payload["title"]
        curated_ids.update(ids)
        report["collections"][tag] = len(ids)
    assert all(len(curation["collections"][tag]) == count for tag, count in [("french50", 50), ("italian50", 50), ("kungfu50", 50), ("shaw_kungfu20", 20)])
    for theme in [None, "drama", "horror", "animation", "blackwhite", "international"]:
        query = {"homepage": "true", "ordering": "rating"}
        if theme:
            query["theme"] = theme
        view = MovieListView()
        view.request = Request(APIRequestFactory().get("/api/v1/movies/", query))
        selected = list(view.get_queryset())
        assert selected and len({movie.tmdb_id for movie in selected}) == len(selected)
        assert all(movie.is_homepage_eligible and movie.vote_count >= 200 for movie in selected)
        assert [movie.tmdb_id for movie in selected] == [movie.tmdb_id for movie in sorted(selected, key=lambda m: (-m.vote_average, -m.vote_count, m.tmdb_id))]
        if theme in {"drama", "horror", "animation"}:
            genre = {"drama": 18, "horror": 27, "animation": 16}[theme]
            assert all(genre in {g.tmdb_id for g in movie.genres.all()} for movie in selected)
        if theme == "blackwhite":
            assert all(Movie.Source.BLACKWHITE in movie.source_tags for movie in selected)
        if theme == "international":
            assert all(movie.original_language not in {"en", "", "xx", "zxx"} for movie in selected)
        report["homepage"][theme or "all"] = len(selected)
    manifest = read("data/phase8/trailer_manifest_500.json")
    rows = manifest["movies"]
    assert len(rows) == len({row["tmdb_id"] for row in rows}) == 500
    for row in rows:
        mid = row["tmdb_id"]
        movie = movies[mid]
        assert mid in source_ids
        assert {"letterboxd_top1000", "tspdt_top1000"} <= set(memberships[mid])
        assert row["title"] == movie.title and row["year"] == movie.release_date.year
        assert row["source_memberships"] == "; ".join(sorted(memberships[mid]))
        assert row["source_ranks"] == "; ".join(f"{source}: {memberships[mid][source]}" for source in sorted(memberships[mid]))
        assert movie.trailer_key and row["trailer_url"] == f"https://www.youtube.com/watch?v={movie.trailer_key}"
        assert row["required_filename"] == f"{mid}.mp4"
        assert Path(row["destination_folder"]).resolve() == (ROOT / "data/raw/trailers").resolve()
    content = get_content_service()
    assert len(content.movie_ids) == len(movies) and all(content.contains(mid) for mid in movies)
    assert MovieDetailSerializer().get_letterboxd_embed_url(movies[238]) == "https://embed.letterboxd.com/tmdb/238/embed-histogram/?theme=dark&noTitle=true"
    report.update(passed=True, catalog_movies=len(movies), scraped_movies=len(source_ids), curated_movies=len(curated_ids), citations=TechniqueSourceCitation.objects.count(), original_ids_and_ranks_preserved=True, selected_trailers=500, content_model_movies=len(content.movie_ids))
    write_json(ROOT / "data/expansion/catalog-verification.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        connection.close()
