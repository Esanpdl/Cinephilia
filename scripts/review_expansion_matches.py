"""Verify ambiguous list matches using each supplied Letterboxd film's TMDB link."""
import json
from pathlib import Path
import re
from fetch_expansion_lists import fetch

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "data/expansion/lists"
review = json.loads((folder / "review.json").read_text(encoding="utf-8"))
path = folder / "decisions.json"
decisions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"input_hashes": review["input_hashes"], "decisions": {}}
for entry in review["entries"]:
    if entry["key"] in decisions["decisions"]:
        continue
    body = fetch(entry["source_item_url"])
    ids = set(re.findall(r'https://(?:www\.)?themoviedb\.org/(movie|tv)/(\d+)', body))
    if len(ids) != 1:
        raise ValueError(f"{entry['key']}: film page has no unique TMDB identity: {ids}")
    kind, number = ids.pop()
    decision = {"tmdb_id": int(number) if kind == "movie" else None, "reason": "Identity verified using the exact scraped Letterboxd film page's TMDB link, not title-search position.", "evidence_url": entry["source_item_url"]}
    if kind == "tv":
        decision["tmdb_tv_id"] = int(number)
    decisions["decisions"][entry["key"]] = decision
    path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{entry['key']}: {kind} {number}", flush=True)
