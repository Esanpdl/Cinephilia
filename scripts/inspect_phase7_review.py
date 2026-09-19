"""Collect extra authentic TMDB evidence for unresolved source identities."""
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from apps.movies.services.tmdb import TMDBClient, write_json
from apps.cinematography.services.source_lists import SOURCES, load_source
import hashlib

sources = [load_source(ROOT / "data/raw/technique_sources" / f"{source}.json") for source in SOURCES]
hashes = {source.source: source.digest for source in sources}
directory = ROOT / "data/phase7" / hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:20]
review = json.loads((directory / "review.json").read_text(encoding="utf-8"))["entries"]
client = TMDBClient()
def inspect(entry):
    result = client.get("/search/multi", {"query": entry["match_title"], "language": client.language, "include_adult": "true"})
    candidates = []
    movie_candidates = entry["resolution"].get("candidates", [])[:3]
    for movie in movie_candidates:
        payload = client.details(movie["tmdb_id"])
        candidates.append({"id": payload["id"], "type": "movie", "title": payload["title"], "date": payload.get("release_date"), "runtime": payload.get("runtime"), "directors": [person["name"] for person in payload["credits"]["crew"] if person.get("job") == "Director"], "adult": payload.get("adult")})
        write_json(directory / "review_details" / f"{payload['id']}.json", payload)
    return {"key": entry["key"], "source_title": entry["title"], "source_director": entry["director"], "source_year": entry["year"], "search": [{"id": item["id"], "type": item["media_type"], "title": item.get("title", item.get("name")), "date": item.get("release_date", item.get("first_air_date"))} for item in result["results"][:8]], "details": candidates}
try:
    if "--audit-auto-titles" in sys.argv:
        from apps.cinematography.services.source_lists import fuzzy_title_agrees, title_key
        plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))["results"]
        suspicious = []
        for source in sources:
            for entry in source.entries:
                result = plan[entry["key"]]
                if result["status"] != "resolved" or result["method"] == "reviewed":
                    continue
                movie_id = result["tmdb_id"]
                detail = json.loads((directory / "details" / f"{movie_id}.json").read_text(encoding="utf-8"))
                names = [detail["title"], detail.get("original_title", "")]
                if not any(fuzzy_title_agrees(entry["match_title"], name) for name in names):
                    names += [item["title"] for item in client.alternative_titles(movie_id)["titles"]]
                    if not any(fuzzy_title_agrees(entry["match_title"], name) for name in names):
                        suspicious.append({"key": entry["key"], "title": entry["title"], "tmdb_id": movie_id, "tmdb_title": detail["title"]})
        write_json(directory / "automatic-title-audit.json", {"suspicious": suspicious})
        print(json.dumps({"suspicious": suspicious}, ensure_ascii=True))
        sys.exit(bool(suspicious))
    if "--final-identities" in sys.argv:
        for movie_id in [697, 420240, 94528, 43118]:
            payload = client.details(movie_id)
            write_json(directory / "review_details" / f"{movie_id}.json", payload)
            print(json.dumps({"id": movie_id, "title": payload["title"], "date": payload.get("release_date"), "runtime": payload.get("runtime"), "directors": [p["name"] for p in payload["credits"]["crew"] if p.get("job") == "Director"]}, ensure_ascii=True))
        for tv_id in [206647, 42699, 43189, 1920, 43059]:
            payload = client.get(f"/tv/{tv_id}", {"language": client.language})
            write_json(directory / "excluded_tv" / f"{tv_id}.json", payload)
            print(json.dumps({"tv_id": tv_id, "name": payload["name"], "date": payload.get("first_air_date"), "creators": payload.get("created_by")}, ensure_ascii=True))
        season = client.get("/tv/1920/season/3", {"language": client.language})
        write_json(directory / "excluded_tv/1920-season-3.json", season)
        print(json.dumps({"season": season["season_number"], "date": season["air_date"], "episodes": len(season["episodes"])}))
        sys.exit(0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inspect, review))
    write_json(directory / "extra-review-evidence.json", results)
    for result in results:
        print(json.dumps(result, ensure_ascii=True))
finally:
    client.close()
