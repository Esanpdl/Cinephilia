"""Validate user-scraped identification lists and deduplicate before TMDB lookup."""
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse

SOURCES = {
    "letterboxd_top1000": "https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/",
    "tspdt_top1000": "https://theyshootpictures.com/gf1000_rank1-1000.htm",
}
EXTRA_SOURCES = {
    "letterboxd_animation250": "https://letterboxd.com/official/list/top-250-animated-films/",
    "letterboxd_blackwhite100": "https://letterboxd.com/sean_chavel/list/best-black-white-cinematography-ever/",
}
ALL_SOURCES = {**SOURCES, **EXTRA_SOURCES}
SOURCE_COUNTS = {**dict.fromkeys(SOURCES, 1000), "letterboxd_animation250": 250, "letterboxd_blackwhite100": 100}
ITEM_FIELDS = {"rank", "title", "year", "director", "source_page_url", "source_item_url"}
LIST_URLS = {key: {value} for key, value in ALL_SOURCES.items()}
LIST_URLS["tspdt_top1000"].update({
    "https://theyshootpictures.com/gf1000_all1000films.htm",
    "https://theyshootpictures.com/gf1000_all1000films_table.php",
})


class SourceError(ValueError):
    pass


@dataclass
class SourceList:
    path: Path
    digest: str
    payload: dict

    @property
    def source(self):
        return self.payload["source"]

    @property
    def entries(self):
        return [dict(item, match_title=matching_title(item), source=self.source, key=f"{self.source}:{item['rank']}") for item in self.payload["items"]]


def valid_source_url(value, source):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    host = urlparse(ALL_SOURCES[source]).hostname
    return parsed.scheme == "https" and parsed.hostname in {host, "www." + host} and not parsed.username and not parsed.password and len(value) <= 2000


def load_source(path, allow_incomplete=False):
    path = Path(path)
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError) as error:
        raise SourceError(f"Cannot read source JSON: {path.name}: {error}") from None
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise SourceError(f"{path.name}: expected schema_version 1.")
    source = payload.get("source")
    if source not in ALL_SOURCES or payload.get("source_list_url") not in LIST_URLS[source]:
        raise SourceError(f"{path.name}: unsupported source or canonical list URL.")
    try:
        timestamp = payload["retrieved_at"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            raise ValueError
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        raise SourceError(f"{path.name}: retrieved_at must be the actual UTC timestamp ending in Z.") from None
    items = payload.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 1000 or type(payload.get("actual_count")) is not int or payload["actual_count"] != len(items):
        raise SourceError(f"{path.name}: actual_count must equal 1–1000 source entries.")
    if type(payload.get("complete")) is not bool:
        raise SourceError(f"{path.name}: complete must be a boolean.")
    if not payload["complete"] and not allow_incomplete:
        raise SourceError(f"{path.name}: scrape is incomplete; inspect its report before explicitly using --allow-incomplete.")
    ranks = []
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise SourceError(f"{path.name}: each entry must use the six fields in docs/scraping-handoff-prompt.md.")
        rank, title, year, director = (item[key] for key in ("rank", "title", "year", "director"))
        if type(rank) is not int or not 1 <= rank <= 1000:
            raise SourceError(f"{path.name}: invalid current rank.")
        if not isinstance(title, str) or not title.strip() or len(title) > 500 or "{{" in title or "}}" in title:
            raise SourceError(f"{path.name}: invalid title at rank {rank}.")
        if year is not None and (type(year) is not int or not 1800 <= year <= 9999):
            raise SourceError(f"{path.name}: year at rank {rank} must be a single integer or null.")
        if director is not None and (not isinstance(director, str) or not director.strip() or len(director) > 1000):
            raise SourceError(f"{path.name}: invalid director at rank {rank}.")
        if not valid_source_url(item["source_page_url"], source) or item["source_item_url"] is not None and not valid_source_url(item["source_item_url"], source):
            raise SourceError(f"{path.name}: invalid source URL at rank {rank}.")
        ranks.append(rank)
    if len(set(ranks)) != len(ranks) or ranks != sorted(ranks):
        raise SourceError(f"{path.name}: ranks must be unique and ordered.")
    if payload["complete"] and ranks != list(range(1, SOURCE_COUNTS[source] + 1)):
        raise SourceError(f"{path.name}: a complete list requires all {SOURCE_COUNTS[source]} source positions.")
    return SourceList(path.resolve(), hashlib.sha256(raw).hexdigest(), payload)


def matching_title(item):
    title = item["title"].strip()
    # Strip only a trailing annotation that agrees with a supplied source year.
    suffix = f" ({item['year']})"
    return title[:-len(suffix)] if item["year"] and title.endswith(suffix) else title


def title_key(value):
    # Preserve digits and meaningful words; normalize accents, punctuation and
    # the trailing-article convention used by some source lists.
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("'", "").replace("’", "")
    value = re.sub(r"^(.+),\s*(the|an|a)$", r"\2 \1", value.strip())
    return " ".join("".join(char if char.isalnum() else " " for char in value).split())


def similarity(left, right):
    return SequenceMatcher(None, title_key(left), title_key(right), autojunk=False).ratio()


def numerals(title):
    return [word for word in title_key(title).split() if any(char.isdigit() for char in word) or word in {"ii", "iii", "iv", "vi", "vii", "viii", "ix"}]


def fuzzy_title_agrees(left, right, threshold=.94):
    return numerals(left) == numerals(right) and similarity(left, right) >= threshold


def validate_unique_source_matches(entries, results):
    seen = {}
    for entry in entries:
        result = results.get(entry["key"], {})
        if result.get("status") != "resolved":
            continue
        identity = (entry["source"], result["tmdb_id"])
        if identity in seen:
            raise SourceError(f"Same-source identity collision: {seen[identity]} and {entry['key']} map to TMDB {identity[1]}. Review before importing.")
        seen[identity] = entry["key"]


def director_agrees(left, right):
    if not left or not right:
        return False
    return title_key(left) == title_key(right)


def safe_pair(left, right):
    # Missing-year titles can denote remakes. Exact title alone is not enough
    # to merge source records before their TMDB identities have been verified.
    if left["source"] == right["source"]:
        return False
    same_year = left["year"] is not None and left["year"] == right["year"]
    same_director = director_agrees(left["director"], right["director"])
    if left["year"] and right["year"] and left["year"] != right["year"]:
        return False
    if left["director"] and right["director"] and not same_director:
        return False
    score = similarity(left["match_title"], right["match_title"])
    fuzzy_safe = (score >= .96 and same_year
                  and min(len(title_key(left["match_title"])), len(title_key(right["match_title"]))) >= 12
                  and numerals(left["match_title"]) == numerals(right["match_title"]))
    return (score == 1 and (same_year or same_director)) or fuzzy_safe


def deduplicate(entries):
    """Conservative mutual-unique cross-source pairing; no transitive merges."""
    pairs = {entry["key"]: [] for entry in entries}
    names = list(dict.fromkeys(entry["source"] for entry in entries))
    if len(names) != 2:
        raise SourceError("Pre-TMDB deduplication expects two source lists.")
    by_source = {source: [entry for entry in entries if entry["source"] == source] for source in names}
    # Year and normalized-title blocks avoid a million fuzzy string comparisons.
    right_years, right_titles = {}, {}
    for entry in by_source[names[1]]:
        right_years.setdefault(entry["year"], []).append(entry)
        right_titles.setdefault(title_key(entry["match_title"]), []).append(entry)
    for left in by_source[names[0]]:
        candidates = {entry["key"]: entry for entry in right_titles.get(title_key(left["match_title"]), [])}
        if left["year"] is not None:
            candidates.update({entry["key"]: entry for entry in right_years.get(left["year"], [])})
        for right in candidates.values():
            if safe_pair(left, right):
                pairs[left["key"]].append(right["key"])
                pairs[right["key"]].append(left["key"])
    lookup = {entry["key"]: entry for entry in entries}
    seen, groups = set(), []
    for entry in entries:
        key = entry["key"]
        if key in seen:
            continue
        members = [entry]
        if len(pairs[key]) == 1 and pairs[pairs[key][0]] == [key]:
            members.append(lookup[pairs[key][0]])
        seen.update(member["key"] for member in members)
        groups.append(members)
    return groups
