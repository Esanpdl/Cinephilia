# Phase 7 — Scraped source lists and catalog enrichment

## Import results

| Measure | Verified result |
| --- | ---: |
| Original citations | 2,000 |
| Groups after pre-TMDB deduplication | 1,447 |
| Resolved movie citations | 1,990 |
| Distinct source movies | 1,407 |
| Movies cited by both sources | 583 |
| Existing movies refreshed | 1,018 |
| New movies added | 389 |
| Total shared catalog | 10,388 |
| Preserved TV citations | 9 |
| Preserved unmatched citations | 1 |
| Source movies missing posters | 0 |
| Source movies without a TMDB trailer | 143 |

The repeated import added **zero movies, snapshots or citations**, and changed no
source flags. `initial-import-report.json` preserves the first import receipt;
`report.json` records the latest replay. Database checks confirm all 2,000 raw
citations, original movie IDs/ranks, user data and trained model pointers survive.
Source validation has 13 passing checks; search/range validation has seven passing
checks against the real database. Search pages and batched detail serialization
each use three data queries.
The frontend production build passes. All three focused browser scenarios pass:
shared people search ordering, a newly imported film page, and release-year ranges
including saved URLs, clear/reset and mobile width. Browser receipts are retained
in `data/phase7/browser-initial-results.json` (first two passes) and
`data/phase7/browser-results.json` (the focused year-range pass after correcting
the test's native-option disabled assertion).

## Pipeline

The two user-supplied files in `data/raw/technique_sources/` are retained unchanged.
The pipeline validates their schema, completeness, source URLs and ranks, merges
safe cross-source title/year/director matches, then searches TMDB for every unique
group. It downloads full movie details, credits, genres, keywords and videos using
the same TMDB client, normalizer, trailer selection and database upsert as Phase 2.

`merged.json` is written **before TMDB lookup**. Conservative fuzzy matching keeps
remakes and numbered parts separate. Remaining alternate titles converge on their
verified TMDB IDs. Ambiguous identities require an explicit reviewed decision with
an evidence URL and the exact input-file hashes. A same-source ID collision blocks
import. Reviewed TV entries and unmatched complete works keep their original
citations without a `Movie` link.

Full TMDB evidence remains in `data/phase7/1bfb521f24cd2ecb715b/`:

- `validation.json`, `merged.json`: source hashes and pre-lookup deduplication.
- `plan.json`, `decisions.json`, `review.json`: every match and reviewed exception.
- `details/`, `enriched_movies.json`: full authentic movie payloads and merged citations.
- `excluded_tv/`: verified series/season metadata for excluded citations.
- `automatic-title-audit.json`: audit of automatically accepted title matches.
- `report.json`, `verification.json`: database import and invariant checks.

Large payloads are Git-ignored but retained inside the project for teacher review.
The importer, reviewer helper, recorded final decisions and verification scripts
are ordinary project source files. Earlier training code and model artifacts remain
in `training/`, `artifacts/`, `data/content/` and `data/collaborative/`.

## Supabase storage and duplicate prevention

`TechniqueSourceSnapshot` stores each entire raw JSON payload and its SHA-256 hash.
`TechniqueSourceCitation` stores every rank, raw title, source year/director, source
URLs, match evidence, status and optional canonical movie foreign key.

PostgreSQL enforces unique movie TMDB IDs, unique source/hash snapshots and unique
snapshot/rank citations. Resolved citations must link a movie; excluded/unmatched
citations must have no movie link. A transaction and the shared catalog-import
advisory lock protect the combined update. Re-importing the same evidence refreshes
metadata without adding duplicate movies or citations. A changed identity mapping
for an already imported snapshot is rejected for explicit investigation.

All matched movies receive only the source flags evidenced by their citations.
Existing movie primary keys, Phase 2 ranks, ratings and watchlists are preserved.
New source movies have no Phase 2 catalog rank. The 200-vote discover threshold
applies to the original ranked catalog, not these independently supplied lists.

## Reviewed exceptions

Nine citations represent eight TMDB TV works: Mr. Scorsese, The Sorrow and the Pity
(on both lists), A Personal Journey with Martin Scorsese Through American Movies,
Histoire(s) du cinéma, Dekalog, Berlin Alexanderplatz, Twin Peaks: The Return, and
Heimat. The Return retains its exact season 3 identity and 2017 air date.

Olympia (TSPDT rank 988) remains **unmatched**, as explicitly requested: the source
lists one combined work, while TMDB has separate parts. Neither part is imported
or source-flagged because of that citation.

Complete TMDB movie records were verified for Out 1 and Dog Star Man. Scenes from
a Marriage maps to the theatrical film: the scraped page specifies its film-cut
runtime. Ivan the Terrible Parts I and II map to separate movie IDs. Original
source years remain in citations even when TMDB's primary release year differs.
For example, Criterion documents [A Day in the Country's 1936 production and 1946 release](https://www.criterion.com/films/28072-a-day-in-the-country).

## Availability on the site

Matched films use the shared catalog immediately: browse/search, individual film
pages, posters/trailers when TMDB supplies them, ratings and watchlists. The API
exposes `is_technique_source` and detail `source_tags`. Source citations remain
available in Supabase and the read-only Django admin. The dedicated learning
explorer and its interface are scheduled for Phase 9.

TMDB enrichment cannot guarantee that every film has a trailer or poster. Missing
media stays absent, and the existing UI displays its unavailable-media state.
The current trained models are unchanged; newly added films have no newly trained
content/CF representation. Existing recommendation coverage fallbacks still apply.

### Requested search extension

`GET /api/v1/movies/?q=chaplin` searches title/original title, director and cast names
case-insensitively. Each movie appears once, in its highest matching priority:

1. Title match.
2. Director match.
3. Actor match.

The selected rating/popularity/newest/title order applies within each group. Genre,
year and pagination still work. Empty searches retain the original catalog order.
SQL `EXISTS` checks avoid credit joins multiplying result rows. The browser explains
the priority beside the existing search controls. No director preference is added
to recommendations or homepage selection.

### Release-year range

The same browse filter bar now has **From year** and **To year** selectors, from
1895 through the current UTC year (2026 at verification). The latest option advances
automatically with the year. Set both to the same value for an exact year, or leave
one blank for an open-ended range. Invalid reversed options are disabled. Changes
reset pagination, survive reload in the URL, and combine with genre and people
search. Clear removes both endpoints along with the other active filters.

API parameters are inclusive `year_from` and `year_to`; omitted endpoints default
to 1895/current year when the other endpoint is present. Years outside those bounds
and reversed ranges return field-specific HTTP 400 errors. The legacy exact `year`
parameter and saved browser links remain supported, but the API rejects mixing
`year` with range parameters. Date comparisons operate on the release-date column.
Without any year parameters, the existing unfiltered catalog behavior is retained.

Example: `http://127.0.0.1:5173/browse?q=clint&year_from=1970&year_to=1992`.

## Reproduce and verify

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py import_technique_sources --validate-only
.\.venv\Scripts\python.exe -u backend/manage.py import_technique_sources --decisions data/phase7/1bfb521f24cd2ecb715b/decisions.json
# Review report.json and review.json before applying a new dataset.
.\.venv\Scripts\python.exe -u backend/manage.py import_technique_sources --decisions data/phase7/1bfb521f24cd2ecb715b/decisions.json --apply
.\.venv\Scripts\python.exe scripts/verify_phase7_sources.py
.\.venv\Scripts\python.exe scripts/verify_phase7_database.py
.\.venv\Scripts\python.exe scripts/verify_people_search.py
```

The database check compares against the retained pre-import baseline. Use that
specific baseline only for this dataset and workspace; it is an import audit,
not a general assertion that future user accounts or catalog changes cannot exist.

Open `http://127.0.0.1:5173/browse?q=chaplin` to try people search. Open
`http://127.0.0.1:5173/films/91` for a newly added source film, Land Without Bread.
Its API is `http://127.0.0.1:8000/api/v1/movies/91/`.

Focused browser checks, using an installed Playwright Chromium:

```powershell
Set-Location frontend
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE = 'C:\Users\ishan\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe'
npm.cmd run test:e2e -- --config playwright.phase7.config.ts
```

No trailer files were downloaded and no CV analysis or training was started.
Phase 8 requires the user's separate go-ahead and user-supplied trailer files.
