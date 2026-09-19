"""Auditable TMDB expansion explicitly requested by the project owner.

Stages can resume independently. Source lists are merged before TMDB lookup;
requested TMDB collections never become scraped-source citations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
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
from django.db import connection, transaction
from apps.movies.models import Movie
from apps.movies.services.tmdb import TMDBClient, write_json
from apps.movies.services.catalog import normalize_details, upsert_movies
from apps.cinematography.services.source_lists import EXTRA_SOURCES, load_source, deduplicate, title_key, validate_unique_source_matches
from apps.cinematography.services.resolution import Resolver, manual_result, read_overrides
from apps.cinematography.services.ingestion import apply_plan

OUT = ROOT / "data/expansion"
DIRECTORS = ["Quentin Tarantino", "Martin Scorsese", "Alfred Hitchcock", "Stanley Kubrick", "Billy Wilder", "Akira Kurosawa", "Kiyoshi Kurosawa", "Yasujiro Ozu", "Hayao Miyazaki", "Kenji Mizoguchi", "Satoshi Kon", "Shinya Tsukamoto", "Seijun Suzuki", "David Lynch", "David Cronenberg", "Guillermo del Toro", "John Ford", "Paul Thomas Anderson", "Wong Kar-wai", "Bong Joon-ho", "Park Chan-wook", "Bela Tarr", "Christopher Nolan", "David Fincher", "David Lean"]
# Reviewed against their actual TMDB known works; namesakes are excluded.
REVIEWED_PEOPLE = {
    "Kenji Mizoguchi": 97202,  # Ugetsu, Sansho the Bailiff
    "David Lynch": 5602,  # Mulholland Drive, Blue Velvet
    "John Ford": 8500,  # The Searchers, Stagecoach
    "Wong Kar-wai": 12453,  # In the Mood for Love, Chungking Express
    "Park Chan-wook": 10099,  # Oldboy, The Handmaiden
    "Christopher Nolan": 525,  # Inception, The Dark Knight
}


def read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def released(payload):
    value = payload.get("release_date") or ""
    return "1895-01-01" <= value <= date.today().isoformat() and not payload.get("adult") and not payload.get("video")


def resolve_lists(client):
    sources = [load_source(ROOT / "data/raw/technique_sources" / f"{source}.json") for source in EXTRA_SOURCES]
    entries = [entry for source in sources for entry in source.entries]
    hashes = {source.source: source.digest for source in sources}
    groups = deduplicate(entries)
    folder = OUT / "lists"
    write_json(folder / "merged.json", {"input_hashes": hashes, "groups": groups})
    plan = read(folder / "plan.json", {"input_hashes": hashes, "results": {}})
    if plan["input_hashes"] != hashes:
        raise ValueError("Source files changed; preserve the old run before making a new plan.")
    resolver = Resolver(client, folder)
    decisions_path = folder / "decisions.json"
    overrides = read_overrides(decisions_path if decisions_path.exists() else None, hashes, {entry["key"] for entry in entries})
    for key, decision in overrides.items():
        plan["results"][key] = manual_result(decision, resolver)
    pending = [[entry for entry in group if entry["key"] not in plan["results"]] for group in groups]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(resolver.resolve, group): group for group in pending if group}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            for entry in futures[future]:
                plan["results"][entry["key"]] = result
            write_json(folder / "plan.json", plan)
            if index % 25 == 0:
                print(f"New lists: resolved {index}/{len(futures)} groups", flush=True)
    write_json(folder / "plan.json", plan)
    validate_unique_source_matches(entries, plan["results"])
    review = [dict(entry, resolution=plan["results"][entry["key"]]) for entry in entries if plan["results"][entry["key"]]["status"] not in {"resolved", "excluded", "unmatched"}]
    write_json(folder / "review.json", {"input_hashes": hashes, "entries": review})
    print(f"New lists: {len(entries)} citations, {len(groups)} pre-lookup groups, {len(review)} need review", flush=True)
    return sources, entries, plan, resolver, review


def curated(client):
    path = OUT / "curation.json"
    result = read(path, {"collections": {}, "people": {}, "exclusions": []})
    resolver = Resolver(client, OUT / "curated")
    for name in DIRECTORS:
        if name in result["people"]:
            continue
        response = client.get("/search/person", {"query": name, "include_adult": "false"})
        # Satoshi Kon is categorized as Writing; verify actual directing credits.
        candidates = [p for p in response["results"] if title_key(p["name"]) == title_key(name)]
        if name in REVIEWED_PEOPLE:
            candidates = [p for p in candidates if p["id"] == REVIEWED_PEOPLE[name]]
        if len(candidates) != 1:
            write_json(OUT / "person-review.json", {"name": name, "candidates": response["results"]})
            raise ValueError(f"Director identity needs review: {name}")
        person = candidates[0]
        detail = client.get(f"/person/{person['id']}")
        credits = client.get(f"/person/{person['id']}/movie_credits", {"language": client.language})
        write_json(OUT / "people" / f"{person['id']}.json", {"person": detail, "credits": credits})
        ids = sorted({entry["id"] for entry in credits["crew"] if entry.get("job") == "Director" and released(entry)})
        valid = []
        for movie_id in ids:
            movie = resolver.detail(movie_id)
            if released(movie) and any(p["id"] == person["id"] and p.get("job") == "Director" for p in movie["credits"]["crew"]):
                valid.append(movie_id)
            else:
                result["exclusions"].append({"tmdb_id": movie_id, "requested_director": name, "reason": "Full details do not verify a released movie with this directing credit"})
        result["people"][name] = {"tmdb_id": person["id"], "name": detail["name"]}
        result["collections"][f"director:{person['id']}"] = valid
        write_json(path, result)
        print(f"{name}: {len(valid)} verified directed movies", flush=True)

    keyword_response = client.get("/search/keyword", {"query": "kung fu"})
    keywords = [item for item in keyword_response["results"] if item["name"].casefold() == "kung fu"]
    if len(keywords) != 1:
        raise ValueError("Exact kung fu keyword identity needs review")
    keyword = keywords[0]["id"]
    company_response = client.get("/search/company", {"query": "Shaw Brothers"})
    companies = [item for item in company_response["results"] if item["name"].casefold() == "shaw brothers" and item.get("origin_country") == "HK"]
    if len(companies) != 1:
        write_json(OUT / "company-review.json", company_response)
        raise ValueError("Shaw Brothers company identity needs review")
    company = companies[0]["id"]
    write_json(OUT / "collection-identities.json", {"kung_fu_keyword": keywords[0], "shaw_brothers": client.get(f"/company/{company}")})
    definitions = {
        "french50": (50, {"with_origin_country": "FR", "with_original_language": "fr", "vote_count.gte": 200}),
        "italian50": (50, {"with_origin_country": "IT", "with_original_language": "it", "vote_count.gte": 200}),
        "kungfu50": (50, {"with_keywords": str(keyword), "vote_count.gte": 200}),
        "shaw_kungfu20": (20, {"with_companies": str(company), "with_keywords": str(keyword), "vote_count.gte": 0}),
    }
    for tag, (limit, filters) in definitions.items():
        if tag in result["collections"]:
            continue
        found = {}
        for page in range(1, 501):
            params = {"language": client.language, "include_adult": "false", "include_video": "false", "sort_by": "vote_average.desc", "primary_release_date.lte": date.today().isoformat(), "primary_release_date.gte": "1895-01-01", "page": page, **filters}
            response = client.get("/discover/movie", params)
            write_json(OUT / "discover" / f"{tag}-{page}.json", {"params": params, "response": response})
            for entry in response["results"]:
                if released(entry):
                    movie = resolver.detail(entry["id"])
                    if released(movie):
                        found[entry["id"]] = movie
            ranked = sorted(found.values(), key=lambda movie: (-movie["vote_average"], -movie["vote_count"], movie["id"]))
            if page >= response["total_pages"] or len(ranked) >= limit and response["results"][-1]["vote_average"] < ranked[limit - 1]["vote_average"]:
                break
        if len(ranked) < limit and tag != "shaw_kungfu20":
            raise ValueError(f"{tag}: only {len(ranked)} meet the recorded criteria; review threshold explicitly")
        result["collections"][tag] = [movie["id"] for movie in ranked[:limit]]
        result.setdefault("selection_rules", {})[tag] = {"limit": limit, "filters": filters, "ordering": ["vote_average descending", "vote_count descending", "tmdb_id ascending"]}
        write_json(path, result)
        print(f"{tag}: {len(result['collections'][tag])} movies", flush=True)
    return result, resolver


@transaction.atomic
def apply_curated(result, resolver):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(174839201)")
        if not cursor.fetchone()[0]:
            raise ValueError("Another catalog import holds the lock")
    ids = sorted({mid for movies in result["collections"].values() for mid in movies})
    existing = dict(Movie.objects.filter(tmdb_id__in=ids).values_list("tmdb_id", "catalog_rank"))
    for offset in range(0, len(ids), 100):
        batch = ids[offset:offset + 100]
        upsert_movies([normalize_details(resolver.detail(mid), resolver.client.language) for mid in batch], {mid: existing.get(mid) for mid in batch})
        print(f"Curated catalog: updated {min(offset + 100, len(ids))}/{len(ids)}", flush=True)
    movies = Movie.objects.in_bulk(ids, field_name="tmdb_id")
    for tag, members in result["collections"].items():
        for mid in members:
            movies[mid].curation_tags = sorted(set(movies[mid].curation_tags) | {tag})
    Movie.objects.bulk_update(movies.values(), ["curation_tags"], batch_size=500)
    return {"distinct_movies": len(ids), "new_movies": len(set(ids) - set(existing)), "collection_counts": {key: len(value) for key, value in result["collections"].items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["lists", "curated", "apply-lists", "apply-curated", "inspect-people"])
    args = parser.parse_args()
    client = TMDBClient()
    try:
        if args.stage == "inspect-people":
            for name in DIRECTORS:
                payload = client.get("/search/person", {"query": name, "include_adult": "false"})
                candidates = [p for p in payload["results"] if title_key(p["name"]) == title_key(name)]
                if len(candidates) != 1:
                    print(json.dumps({"name": name, "candidates": [{"id": p["id"], "name": p["name"], "department": p.get("known_for_department"), "known_for": [movie.get("title", movie.get("name")) for movie in p.get("known_for", [])]} for p in payload["results"]]}, ensure_ascii=True), flush=True)
            return
        if "lists" in args.stage:
            sources, entries, plan, resolver, review = resolve_lists(client)
            if args.stage == "apply-lists":
                if review:
                    raise ValueError("Review remaining list identities before applying")
                receipt = apply_plan(sources, entries, plan["results"], resolver, progress=print)
                write_json(OUT / "lists/import-report.json", receipt)
                print(json.dumps(receipt))
        else:
            result, resolver = curated(client)
            if args.stage == "apply-curated":
                receipt = apply_curated(result, resolver)
                write_json(OUT / "curated/import-report.json", receipt)
                print(json.dumps(receipt))
    finally:
        client.close()
        connection.close()


if __name__ == "__main__":
    main()
