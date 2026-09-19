"""Select exactly 500 real scraped-source films and write a download manifest.

No video is downloaded and no CV analysis runs here.
"""
import csv
from datetime import datetime, timezone
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
from apps.cinematography.models import TechniqueSourceCitation, TechniqueSourceSnapshot
from apps.cinematography.services.source_lists import ALL_SOURCES
from apps.movies.models import Movie
from apps.movies.services.tmdb import write_json


def main():
    citations = {}
    for movie_pk, source, rank in TechniqueSourceCitation.objects.filter(status="resolved", snapshot__source__in=ALL_SOURCES).values_list("movie_id", "snapshot__source", "rank"):
        citations.setdefault(movie_pk, {})[source] = rank
    movies = list(Movie.objects.filter(pk__in=citations))
    originals = {"letterboxd_top1000", "tspdt_top1000"}

    def priority(movie):
        ranks = citations[movie.pk]
        both = originals <= set(ranks)
        # Preserve the original both-source priority; choose downloadable trailers
        # within that tier before lower-ranked entries with no TMDB trailer.
        mean_rank = sum(ranks[source] for source in originals if source in ranks) / max(1, len(originals & set(ranks))) if originals & set(ranks) else min(ranks.values())
        return (not both, not bool(movie.trailer_key), mean_rank, -len(ranks), movie.tmdb_id)

    selected = sorted(movies, key=priority)[:500]
    if len(selected) != 500 or len({movie.tmdb_id for movie in selected}) != 500:
        raise ValueError("Exactly 500 distinct scraped films are required; never pad with TMDB-only additions.")
    destination = ROOT / "data/raw/trailers"
    destination.mkdir(parents=True, exist_ok=True)
    output = ROOT / "data/phase8"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for position, movie in enumerate(selected, 1):
        ranks = citations[movie.pk]
        assert movie.is_technique_source and set(ranks) <= set(movie.source_tags)
        rows.append({
            "selection_rank": position, "title": movie.title,
            "year": movie.release_date.year if movie.release_date else "",
            "tmdb_id": movie.tmdb_id,
            "source_memberships": "; ".join(sorted(ranks)),
            "source_ranks": "; ".join(f"{source}: {ranks[source]}" for source in sorted(ranks)),
            "tmdb_url": f"https://www.themoviedb.org/movie/{movie.tmdb_id}",
            "trailer_url": f"https://www.youtube.com/watch?v={movie.trailer_key}" if movie.trailer_key else "",
            "required_filename": f"{movie.tmdb_id}.mp4",
            "destination_folder": str(destination),
        })
    with (output / "trailer_manifest_500.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "eligible_scraped_movies": len(movies), "selected": len(rows), "both_original_sources": sum(originals <= set(citations[movie.pk]) for movie in selected), "available_tmdb_trailer_links": sum(bool(row["trailer_url"]) for row in rows), "tmdb_only_additions_selected": 0, "sources": list(TechniqueSourceSnapshot.objects.filter(source__in=ALL_SOURCES).values("source", "sha256", "actual_count")), "selection_rule": "Both original source lists first; available TMDB trailer within each tier; ascending mean original-source rank, then source count and TMDB ID", "destination_folder": str(destination), "movies": rows}
    write_json(output / "trailer_manifest_500.json", report)
    lines = ["# Film-student trailer download list — 500 films", "", f"Save files in `{destination}`.", "", "Use the exact `<tmdb_id>.mp4` filename below. Supply the actual trailer for that film as an MP4 video, preferably 720p or 1080p, with its original aspect ratio. Do not use full films or multi-film compilations. Keep missing/unavailable links unfilled and report them so we can review a replacement from the eligible scraped pool.", "", "These are trailer-analysis selections, not claims about the cinematography of entire films. No trailer was downloaded automatically.", "", f"Selected from {len(movies)} scraped-source movies; {report['both_original_sources']} appear on both original lists. {report['available_tmdb_trailer_links']} have a TMDB-supplied trailer link. Source ranks and memberships are preserved in the companion CSV/JSON.", "", "| # | Film | Year | TMDB ID | Trailer | Filename |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        title = row["title"].replace("|", "\\|").replace("\n", " ")
        trailer = f"[Trailer]({row['trailer_url']})" if row["trailer_url"] else "Unavailable in TMDB"
        lines.append(f"| {row['selection_rank']} | {title} | {row['year']} | [{row['tmdb_id']}]({row['tmdb_url']}) | {trailer} | `{row['required_filename']}` |")
    (output / "TRAILER_DOWNLOAD_LIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"movies", "sources"}}, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        connection.close()
