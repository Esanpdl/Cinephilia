# Copy this prompt into another AI with web access and file creation

You are collecting minimal film-identification lists for **Cinephilia**, a college
movie recommendation project. Collect titles and readily available matching clues,
plus rank and source URLs to preserve list membership. Return downloadable
files, not merely instructions or a sample. If your environment cannot access a
source or create files, say so and provide a runnable extraction script instead.
Never claim to have fetched or validated something you did not actually fetch.


## Scope

Collect the current entries from these two exact lists, retaining each source
separately. **Title is the only required movie-metadata field.** Year and director
are optional: capture them only when already present in the list entry. The project
developer will deduplicate these source lists, resolve identities through TMDB,
and use each confirmed TMDB ID to obtain available overview, cast, genres, keywords,
poster and trailer metadata and merge with the existing PostgreSQL catalog.
You only collect the identification lists; do not perform TMDB enrichment yourself.
TMDB matching must later flag ambiguous/unmatched titles instead of guessing.
You do not need TMDB, Supabase, Lightning, or any account/API credentials.

### A. Letterboxd

Source identifier: `letterboxd_top1000`

Canonical list URL:
https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/

- Preserve **List Order**. Do not select popularity, ratings or alphabetical sort.
- The list was observed with 100 entries per page and 10 pages. Verify the current
  pagination, following the actual Next links through the final page. Page 2 uses
  `https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/page/2/`.
- Extract only film-list entries, not titles mentioned in the introduction,
  navigation, recommendations or comments. Get the displayed rank and title.
- The observed grid exposes title and rank but not release year. Use `year: null`
  when missing. Use `director: null` when missing. Do not
  guess these fields from memory, from a title's digits, or from another website.
- Capture a film's canonical Letterboxd URL only if the page actually provides it.
  Do not construct a slug from the title. A missing item URL is allowed.
- For speed, avoid 1,000 separate film-detail requests merely to fill optional
  metadata. The project can resolve missing years and directors through TMDB later.

### B. They Shoot Pictures, Don't They? (TSPDT)

Source identifier: `tspdt_top1000`

Canonical list URL:
https://theyshootpictures.com/gf1000_rank1-1000.htm

Use the official **plain list** linked from that page:
https://theyshootpictures.com/gf1000_all1000films.htm

The official sortable table is another candidate:
https://theyshootpictures.com/gf1000_all1000films_table.php

- The original ranking page returned JavaScript template placeholders during
  inspection. The plain list exposed actual entries directly. Start with the
  plain list and validate what your own request returns; do not invent selectors.
- Extract the leading **current rank** and title. Also keep the director and release
  year when available in the same entry. The following bracketed number is the **previous year's rank**,
  not the current rank and not a release year.
- The plain entries place film information in trailing parentheses. Titles may
  themselves contain punctuation, digits or parentheses. Directors may be plural,
  and years may be ranges. Do not blindly split on every comma or parenthesis.
- Preserve the source's director text, including multiple directors, as one string.
- Put an unambiguous single release year in `year`. For a year range or multipart
  expression, set `year: null` and note the rank and original expression in the
  short extraction report; do not select or invent a single year.
- Keep the original title capitalization and accents. Do not title-case titles.
- Use the site's current **1,000 Greatest Films** list, not its 21st-century list,
  starting list, previous editions, polls, or “ex-1,000” list.
- If the plain list is unavailable, inspect the official sortable table. If neither
  exposes authentic complete entries, stop for this source and report the exact
  obstacle. Never substitute a fan-maintained copy or guessed film list.

## Exact output contract

Create UTF-8 JSON (not CSV, JSONL, or a Markdown code block masquerading as a file).
Use one top-level object per source with these fields:

| Field | Required type and meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `source` | `letterboxd_top1000` or `tspdt_top1000` |
| `source_list_url` | Exact canonical list URL above |
| `retrieved_at` | Actual UTC extraction timestamp in ISO 8601 ending in `Z` |
| `actual_count` | Actual number of extracted items |
| `complete` | Boolean; true only after completeness checks below pass |
| `items` | Array of the item objects specified below, ordered by rank |

Each item has **exactly** these fields:

| Field | Required type and meaning |
| --- | --- |
| `rank` | Integer current source rank, normally 1 through 1000 |
| `title` | Nonempty title exactly as listed, with surrounding whitespace removed |
| `year` | Integer release year if unambiguous and source-provided, otherwise `null` |
| `director` | Source-provided director text, otherwise `null` |
| `source_page_url` | Exact page from which this entry was extracted |
| `source_item_url` | Canonical film-entry URL if actually supplied, otherwise `null` |

Do not collect descriptions, cast lists, genres, reviews, ratings, poster images,
trailer links or trailer files. Do not invent sample rows, TMDB IDs or cinematography
tags. Missing optional year/director fields are acceptable and should stay `null`.
Do not remove the same film from one file
because it also occurs in the other file. Cross-source overlap is valuable evidence.

## Validation

1. Parse the finished files as JSON. Verify required keys/types, nonempty titles,
   actual_count equal to the item count, source consistency and absolute source URLs.
2. For a complete 1,000-entry list, require 1,000 unique ranks covering 1–1000 with
   no gaps. Report duplicate titles/item URLs for review; do not silently collapse
   potentially different films or editions sharing a title.
3. Reconcile page boundaries, especially ranks 100/101 and 900/901 for Letterboxd.
   Make sure a repeated pagination response has not been counted twice.
4. Check first, middle and last entries against retrieved source evidence, including
   several punctuation-heavy titles and any multiple-director or year-range entries.
5. Reject login pages, error pages, empty responses and `{{...}}` template tokens
   as film data. Do not treat a request's HTTP 200 alone as proof of successful extraction.
6. Respect access controls and rate limits, cache fetched pages while processing,
   avoid aggressive parallelism, and do not bypass access blocks.
7. If fewer than 1,000 entries are actually obtainable or the list has changed,
   save only verified entries with `complete: false`, report the reason and ask
   the user what to do. Never pad the file to reach a desired count.

## Files to deliver

Save these paths relative to the **Cinephilia** project root, or deliver a ZIP with
the same relative structure if you do not share the user's filesystem:

```text
data/raw/technique_sources/letterboxd_top1000.json
data/raw/technique_sources/tspdt_top1000.json
data/raw/technique_sources/scrape_report.md
```

The user's absolute destination is:
`C:\Users\ishan\Documents\CollegeProject\Cinephilia\data\raw\technique_sources\`

If you used code, include the small extraction script and requirements so the lists
can be refreshed later. Do not modify the Cinephilia application or database.

Keep `scrape_report.md` short: actual counts, fetched URLs/page counts, missing
optional fields, rank gaps/duplicates, repeated titles and parsing ambiguities,
including any year ranges. State which validation checks passed and whether each
source is complete. Distinguish checks you ran from checks still pending.

In your final reply, link the downloadable files/ZIP and summarize real results.
Keep the complete 2,000-row dataset in files rather than pasting it into chat.
