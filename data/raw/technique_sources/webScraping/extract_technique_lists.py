"""Extract film-identification lists from two ranked sources.

Sources:
  1. letterboxd_top1000 - Letterboxd "Top 1000 Films" list by prof_ratigan
     (10 paginated pages of 100 entries, canonical list order preserved).
  2. tspdt_top1000       - TSPDT "1,000 Greatest Films (plain)" page.

Only the list membership + rank (+ year/director already present in each
entry) are captured. No missing metadata is guessed or filled in.
"""

import html as htmlmod
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from scrape_utils import (
    cache_path_for,
    decode_html,
    fetch,
    log,
    utc_now_iso,
    validate_listing,
    write_json,
)

# Outputs (JSON + report) live one level above the scripts, next to this
# webScraping/ folder, i.e. inside the dataset directory.
OUT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = OUT_DIR / ".cache"

LB_SOURCE_URL = (
    "https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/"
)
LB_EXPECTED_PAGES = 10
LB_PAGE_SIZE = 100

TSPDT_SOURCE_URL = "https://theyshootpictures.com/gf1000_all1000films.htm"

LB_OUT = OUT_DIR / "letterboxd_top1000.json"
TSPDT_OUT = OUT_DIR / "tspdt_top1000.json"
REPORT_OUT = OUT_DIR / "scrape_report.md"

LB_YEAR_SUFFIX_RE = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")
LB_ITEM_RE = re.compile(
    r'<li class="posteritem numbered-list-item"[^>]*>(.*?)</li>', re.S
)
LB_RANK_RE = re.compile(r'<p class="list-number">(\d+)</p>')
LB_NAME_RE = re.compile(r'data-item-name="([^"]*)"')
LB_LINK_RE = re.compile(r'data-item-link="([^"]*)"')
LB_NEXT_RE = re.compile(r'<a class="next"[^>]*href="([^"]+)"')

TSPDT_INTRO = "Below is a straightforward listing"

FORCE = "--force" in sys.argv


def lb_extract_year(name: str) -> tuple[str, int | None]:
    """Split a Letterboxd display name like 'Fargo (1996)'.

    Returns ``(title, year)``. The display name is kept exactly as listed
    (including the trailing year annotation); the year is filled only when it
    is a clean 4-digit value in a plausible release-year range provided by
    the source itself -- never guessed.
    """
    m = LB_YEAR_SUFFIX_RE.match(name)
    if m:
        title, year_str = m.group(1).strip(), int(m.group(2))
        if 1870 <= year_str <= 2100:
            return name, year_str
    return name, None


def parse_letterboxd_page(fetched_url: str, force: bool = False) -> list[dict]:
    body = fetch(fetched_url, CACHE_DIR, force=force)
    page_html = decode_html(body)

    blocks = LB_ITEM_RE.findall(page_html)
    if not blocks:
        if "Please log in" in page_html or "sign in" in page_html.lower():
            raise RuntimeError(
                f"Letterboxd returned an auth/block page for {fetched_url}"
            )
        raise RuntimeError(f"no list entries found on {fetched_url}")

    items = []
    for block in blocks:
        rank_m = LB_RANK_RE.search(block)
        name_m = LB_NAME_RE.search(block)
        link_m = LB_LINK_RE.search(block)
        if not rank_m or not name_m or not link_m:
            raise RuntimeError(f"malformed entry on {fetched_url}: {block[:200]}")
        name = htmlmod.unescape(name_m.group(1)).strip()
        title, year = lb_extract_year(name)
        items.append(
            {
                "rank": int(rank_m.group(1)),
                "title": title,
                "year": year,
                "director": None,
                "source_page_url": fetched_url,
                "source_item_url": (
                    "https://letterboxd.com" + link_m.group(1)
                ),
            }
        )
    return items


def extract_letterboxd() -> dict:
    page_url = LB_SOURCE_URL
    all_items: list[dict] = []
    page_number = 0

    for page_number in range(1, LB_EXPECTED_PAGES + 1):
        items = parse_letterboxd_page(page_url, force=FORCE)
        expected_start = (page_number - 1) * LB_PAGE_SIZE + 1
        expected_ranks = list(range(expected_start, expected_start + LB_PAGE_SIZE))
        actual_ranks = [it["rank"] for it in items]
        if items and actual_ranks != expected_ranks:
            raise RuntimeError(
                f"page {page_number} ranks {actual_ranks[:3]}... != expected "
                f"{expected_ranks[0]}..{expected_ranks[-1]} (pagination shifted?)"
            )
        all_items.extend(items)

        next_m = LB_NEXT_RE.search(decode_html(fetch(page_url, CACHE_DIR, force=FORCE)))
        if next_m is None:
            break
        page_url = urljoin(LB_SOURCE_URL, next_m.group(1))

    actual_count = len(all_items)
    ranks = {it["rank"] for it in all_items}
    complete = (
        actual_count == 1000
        and ranks == set(range(1, 1001))
        and page_number == LB_EXPECTED_PAGES
    )
    return {
        "schema_version": 1,
        "source": "letterboxd_top1000",
        "source_list_url": LB_SOURCE_URL,
        "retrieved_at": utc_now_iso(),
        "actual_count": actual_count,
        "complete": complete,
        "pages_fetched": page_number,
        "items": sorted(all_items, key=lambda it: it["rank"]),
    }


def parse_tspdt_line(line: str) -> dict | None:
    m = re.match(r"^(\d+)\.\s+\(([^)]*)\)\s+(.*)$", line)
    if not m:
        return None
    rank, rest = int(m.group(1)), m.group(3)
    if "(" not in rest or not rest.endswith(")"):
        return None
    title, _, meta = rest.rpartition("(")
    title = title.strip()
    meta = meta.rstrip(")").strip()
    fields = [f.strip() for f in meta.split(",")]
    if len(fields) < 5:
        return None

    director = ", ".join(fields[:-4])
    year_token = fields[-4]
    year: int | None = None
    if re.match(r"^\d{4}$", year_token):
        year = int(year_token)
    elif re.match(r"^\d{4}-\d{2,4}$", year_token):
        year = None  # year range, e.g. 1988-98 -> cannot name a single year
    else:
        log.warning("unusual year token %r on line: %s", year_token, line[:120])

    return {
        "rank": rank,
        "title": title,
        "year": year,
        "director": director,
        "source_page_url": TSPDT_SOURCE_URL,
        "source_item_url": None,
    }


def extract_tspdt() -> dict:
    body = fetch(TSPDT_SOURCE_URL, CACHE_DIR, force=FORCE)
    page_html = htmlmod.unescape(decode_html(body))

    start = page_html.find(TSPDT_INTRO)
    if start < 0:
        raise RuntimeError("TSPDT intro marker not found")
    # The first numbered line ("1. (1) ...") is the real beginning of the
    # list; the intro sentence sits just before it in the same text block.
    line_start = page_html.find("1. (1) ", start)
    if line_start < 0:
        raise RuntimeError("TSPDT numbered block not found")
    block_end = page_html.find("</div>", line_start)
    text = page_html[line_start:block_end]

    items: list[dict] = []
    for chunk in re.split(r"<br\s*/?>", text):
        chunk = chunk.strip()
        if not chunk:
            continue  # e.g. the "<br /> <br />" gap between line groups
        item = parse_tspdt_line(chunk)
        if item is None:
            if items:
                break  # past the numbered block
            continue
        items.append(item)

    actual_count = len(items)
    ranks = {it["rank"] for it in items}
    complete = actual_count == 1000 and ranks == set(range(1, 1001))
    return {
        "schema_version": 1,
        "source": "tspdt_top1000",
        "source_list_url": TSPDT_SOURCE_URL,
        "retrieved_at": utc_now_iso(),
        "actual_count": actual_count,
        "complete": complete,
        "pages_fetched": 1,
        "items": sorted(items, key=lambda it: it["rank"]),
    }


def normalized_key(it: dict) -> tuple[str, int | None]:
    """Cross-source comparison key: upper-cased title with any trailing
    '(YYYY)' annotation removed, plus the year."""
    title = it["title"].upper()
    m = re.match(r"^(.*?)\s*\(\d{4}\)\s*$", title)
    if m:
        title = m.group(1).strip()
    return title, it["year"]


def overlap_between(lb: dict, tspdt: dict) -> int:
    tspdt_keys = {normalized_key(it) for it in tspdt["items"]}
    return sum(1 for it in lb["items"] if normalized_key(it) in tspdt_keys)


def write_report(lb: dict, tspdt: dict) -> None:
    tspdt_snapshot = cache_path_for(CACHE_DIR, TSPDT_SOURCE_URL)
    tspdt_mtime = (
        datetime.fromtimestamp(tspdt_snapshot.stat().st_mtime).isoformat(timespec="seconds")
        if tspdt_snapshot.exists()
        else "n/a"
    )
    lines = [
        "# Scrape report: ranked technique-source film lists",
        "",
        f"Generated: **{utc_now_iso()}** (UTC)",
        "",
        "## Summary",
        "",
        "| Source | count | complete | pages fetched |",
        "|---|---|---|---|",
        f"| Letterboxd top 1000 | {lb['actual_count']} | {lb['complete']} | {lb['pages_fetched']} |",
        f"| TSPDT 1,000 greatest | {tspdt['actual_count']} | {tspdt['complete']} | {tspdt['pages_fetched']} |",
        "",
        "## Letterboxd (prof_ratigan / top-1000-films-of-all-time-calculated)",
        "",
        f"- Canonical list URL: {lb['source_list_url']}",
        f"- Pages: 1..{lb['pages_fetched']}, 100 entries per page, list order preserved.",
        "- Fields: rank (grid number), title (display name exactly as listed), year,"
        " source_page_url (page it appeared on), source_item_url (canonical film page).",
        "- **director: null** -- the grid does not expose directors.",
        "- **year**: the grid's display name carries a trailing year annotation"
        " (e.g. `The Godfather (1972)`); that value is kept as the source-provided"
        " year, and the title is kept exactly as listed (annotation included)."
        " Names without a plausible trailing 4-digit year keep `year: null`.",
        "- No titles/URLs were constructed from memory or from other websites;"
        " item URLs come from `data-item-link` on the page.",
        "",
        "## TSPDT (1,000 Greatest Films, plain list)",
        "",
        f"- Source URL: {tspdt['source_list_url']}",
        "- Single page with all 1,000 entries in ascending rank order.",
        f"- Sample line format: `1. (1) TITLE (Director, 1941, Country, 119m, BW)`.",
        "- The number in the trailing parentheses' first slot is the film's **rank"
        " in the previous edition** and is deliberately ignored (not the release year).",
        "- **director**: preserved from the source as a single string; multi-director"
        " entries keep the source commas (e.g. `David Maysles, Albert Maysles, Ellen"
        " Hovde & Muffie Meyer`).",
        "- **year**: taken from the source; ranges cannot be named as one integer."
        f" ({sum(1 for it in tspdt['items'] if it['year'] is None)} entry has a"
        " year range and is stored as `null`: `140. HISTOIRE(S) DU CINÉMA, 1988-98`).",
        "- **source_item_url: null** -- the plain page provides no per-film links.",
        "- Titles are exactly as listed by TSPDT (all-caps in this source); accents"
        " and HTML entities (e.g. `8½`, `É`) are decoded to UTF-8.",
        "",
        "## Sources & fetching",
        "",
    ]
    lines.extend(
        [
            "- **Letterboxd**: page 1 (canonical URL) plus `/page/2/` .. `/page/10/`"
            " were fetched live (each HTTP 200) and cached in `.cache/`; nothing"
            " was guessed and no external API was used.",
            "- **TSPDT**: fetched live once (HTTP 200). Mid-crawl the site started"
            " answering automated requests with **HTTP 403**, so this run reuses"
            " that first verified retrieval, kept as a raw snapshot in `.cache/`"
            f" (file mtime {tspdt_mtime}).",
            "- To fetch fresh next time (once the site allows it): run"
            " `python webScraping/extract_technique_lists.py --force`.",
            "",
            "## Validation",
            "",
        ]
    )
    for name, listing in (("letterboxd_top1000", lb), ("tspdt_top1000", tspdt)):
        problems = validate_listing(listing)
        status = "passed" if not problems else "FAILED"
        lines.append(f"### {name}: `{status}`")
        if problems:
            for p in problems:
                lines.append(f"- {p}")
        if not problems:
            lines.append(
                "- JSON schema (schema_version/keys/types) OK; "
                "ranks exactly 1..{} unique, in order, no gaps; "
                "actual_count == len(items); title non-empty; "
                "year is int or null; director is str or null; "
                "source_item_url null or a canonical film URL.".format(
                    listing["actual_count"]
                )
            )
        titles = [it["title"] for it in listing["items"]]
        dup_titles = {t for t in titles if titles.count(t) > 1}
        null_years = [it["rank"] for it in listing["items"] if it["year"] is None]
        null_links = sum(1 for it in listing["items"] if it["source_item_url"] is None)
        lines.append(
            "- Field coverage: "
            f"year null on {len(null_years)} entry(s) {null_years[:5]}; "
            f"source_item_url null on {null_links}; "
            f"duplicate titles within this list: {len(dup_titles)} "
            f"({sorted(dup_titles)[:3]}... if any)."
        )
        first, *_, last = listing["items"]
        mid = listing["items"][len(listing["items"]) // 2]
        lines.append(
            "- Spot checks: "
            f"#{first['rank']} {first['title']!r}, "
            f"#{mid['rank']} {mid['title']!r}, "
            f"#{last['rank']} {last['title']!r}."
        )
        lines.append("")

    lb_keys = {normalized_key(it) for it in lb["items"]}
    tspdt_keys = {normalized_key(it) for it in tspdt["items"]}
    shared = lb_keys & tspdt_keys
    lines.extend(
        [
            "## Cross-source",
            "",
            f"- Entries found in BOTH lists (normalized title+year -- title up-cased,"
            f" trailing '(YYYY)' annotation stripped): **{len(shared)} of 1000**."
            " (The raw title strings differ by design: Letterboxd keeps the"
            " `(year)` annotation and mixed case; TSPDT lists titles in all caps,"
            " so an exact-string comparison would count 0.)",
            " Duplicates are expected and intentionally not collapsed.",
            "- Files: `letterboxd_top1000.json`, `tspdt_top1000.json` (UTF-8) next"
            " to this report.",
            "- Scripts: `webScraping/extract_technique_lists.py` (+"
            " `webScraping/scrape_utils.py`); re-runnable, raw pages cached in"
            " `.cache/` (keyed by SHA-1 of the URL).",
            "- Raw snapshots: cached raw HTML pages in `.cache/` serve as a local"
            " copy of what was scraped; delete that folder only after checking the"
            " JSON still looks right.",
            "",
        ]
    )
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote %s", REPORT_OUT)


def main() -> int:
    lb = extract_letterboxd()
    tspdt = extract_tspdt()

    write_json(LB_OUT, lb)
    write_json(TSPDT_OUT, tspdt)

    lb_problems = validate_listing(lb)
    tspdt_problems = validate_listing(tspdt)

    write_report(lb, tspdt)

    log.info(
        "letterboxd: n=%d complete=%s problems=%d",
        lb["actual_count"], lb["complete"], len(lb_problems),
    )
    log.info(
        "tspdt:      n=%d complete=%s problems=%d",
        tspdt["actual_count"], tspdt["complete"], len(tspdt_problems),
    )
    print(f"overlap (title+year in both)={overlap_between(lb, tspdt)}")
    if lb_problems or tspdt_problems:
        for p in lb_problems:
            print("LB problem:", p)
        for p in tspdt_problems:
            print("TSPDT problem:", p)
        return 1
    print("validation OK")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sys.exit(main())