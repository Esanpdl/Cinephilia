# technique_sources -- web scraping scripts

Scripts that built the two ranked film lists in the parent directory:

- `letterboxd_top1000.json` -- Letterboxd "Top 1000 Films of All Time"
  list by [prof_ratigan](https://letterboxd.com/prof_ratigan/)
  (`https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/`).
- `tspdt_top1000.json` -- TSPDT "1,000 Greatest Films"
  (`https://theyshootpictures.com/gf1000_all1000films.htm`).
- `scrape_report.md` -- how the data was gathered and validated.

## What the scripts do

- **`extract_technique_lists.py`** -- entry point. Crawls the 10 paginated
  Letterboxd pages (100 entries each, list order preserved) and the single
  TSPDT plain list, then writes the two JSON files and the scrape report
  into the parent folder.
- **`scrape_utils.py`** -- HTTP fetching (retry/backoff/jitter, timeouts,
  `Retry-After` handling, curl fallback transport), on-disk raw-page caching,
  and schema/rank validation.

Only rank + title (+ year/director when the source entry itself provides
them) are captured. Nothing is guessed from memory or from other sites.

## Requirements

- Python 3.10 or newer. No third-party packages (standard library only).
- `curl` on the PATH is used automatically if a site's bot protection blocks
  requests from `urllib`. Without it the scripts still work via `urllib`.

## How to run

From this folder:

```bash
python extract_technique_lists.py
```

Outputs (written one level up, next to `webScraping/`):

- `letterboxd_top1000.json`
- `tspdt_top1000.json`
- `scrape_report.md`

Raw downloaded pages are cached in `../.cache` (keyed by SHA-1 of each URL),
so re-runs do not re-request the sites:

```bash
# Force a full re-fetch (ignores the cache):
python extract_technique_lists.py --force
```

## How to check the data

The script validates both files before finishing (exit code 0):

- JSON parses; `schema_version` = 1 and all required keys/types present.
- Exactly 1000 unique integer ranks covering 1..1000, in order, no gaps.
- Page boundaries reconcile (Letterboxd pages 1-10, 100 ranks each).
- `title` non-empty; `year` is an integer or `null`; `director` is a string
  or `null`; `source_item_url` is a canonical film URL or `null`.

Both JSON files are plain UTF-8; open them in any text editor or with Python:

```python
import json

with open("../letterboxd_top1000.json", encoding="utf-8") as fh:
    data = json.load(fh)
print(data["actual_count"], data["complete"])
print(data["items"][0])
```

## Notes on the live crawl

TSPDT intermittently answers automated requests with HTTP 403 (here it began
blocking requests from this IP part-way through the crawl). The first, HTTP
200, retrieval was captured and cached, and the cached raw page is reused so
the dataset is complete and reproducible. Subsequent runs re-fetch only when
the site allows it; `--force` retries live fetching.