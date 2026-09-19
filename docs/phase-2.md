# Phase 2 — Core models and TMDB integration

**Status: complete. Awaiting explicit approval for Phase 3.**

## Final catalog audit

- 10,000 unique film IDs selected; **9,999 eligible films stored**.
- One exclusion: **The Lost King** (TMDB 914216). Discovery reported 200 votes,
  while its detail response reported 199. The approved minimum of 200 is retained.
- No missing completed records, unaccounted selected IDs, invalid policy records,
  missing TMDB source tags, or incorrect captured snapshot ranks.
- 9,993 poster paths and 9,264 eligible YouTube trailer keys; missing media stays empty.
- 19 genres, 208,987 people and 380,547 cast/director credits.
- Stored vote averages range from 6.200 to 9.171; minimum stored vote count is 200.
- Zero technique-source flags added by the TMDB import.
- Evidence: `data/tmdb/verification/catalog-audit.json`, the import manifest, and
  The Godfather's raw serializer/media verification JSON in the same folder.

Detail scores can differ from discovery scores because TMDB changes during an
import. The saved manifest preserves captured discovery ranks; the API exposes
stored detail values. No additional title was invented or fetched past page 500
to disguise the one below-threshold exclusion.

## Approved catalog policy

Import up to **10,000** movies with **at least 200 votes**, ordered by descending
TMDB vote average, with **no rating cutoff**. The user chose this over a 7/10 minimum.
This is a rating-ranked catalog, not an editorial classics list.

Use `/discover/movie` with `sort_by=vote_average.desc`, `vote_count.gte=200`,
`vote_average.gte=0`, `include_adult=false`, `include_video=false`, and primary
release date through the snapshot date. Films from all countries and original
languages remain eligible; `en-US` selects metadata language only.

TMDB permits 500 pages / 10,000 results. If fewer unique films qualify, report the
real count without padding. The first live response reported 14,911 eligible films.
The Godfather (TMDB 238) appeared on the first page at 8.687/10 and 23,560 votes.
These are captured API values, not permanent scores.

## Built

| Module | Behavior |
| --- | --- |
| `movies` | Movie, Genre, Person and cast/director credits; unique TMDB identities |
| `ratings` | One integer 1–10 Rating and one WatchlistItem per user/movie pair |
| `users` | Profile, favorite genres and explicit idempotent profile creation |
| `movies/services/tmdb.py` | Token/v3-key auth, retries, pacing, timeouts and JSON cache |
| `movies/services/catalog.py` | Validated transactional bulk upserts, preserving source tags |
| `movies/services/media.py` | TMDB CDN image URLs and YouTube trailer embed URLs |
| `movies/serializers.py` | REST-ready JSON with three-query prefetched detail retrieval |

Tables reside in the private `cinephilia` schema. Database constraints enforce
rating bounds and uniqueness. Indexes support rating order, release date, user
history and source tags. TMDB imports add only `tmdb`; Letterboxd/TSPDT flags are
reserved for actual scraped citations. Missing media produces `null` URLs.

Trailers must be YouTube videos identified as Trailer by TMDB. Prefer the metadata
language, then official status, then recency. No teaser is relabelled as a trailer.
No trailer files are downloaded.

## Run and inspect

From `Cinephilia` with the configured environment:

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py import_tmdb --limit 10000 --min-votes 200 --min-rating 0
.\.venv\Scripts\python.exe backend/manage.py inspect_movie 238
.\.venv\Scripts\python.exe backend/manage.py verify_movie_media 238
.\.venv\Scripts\python.exe scripts/verify_phase2.py
.\.venv\Scripts\python.exe backend/manage.py audit_catalog data/tmdb/imports/catalog-79e1cd4c0fb06175.json
```

`inspect_movie` prints real stored movie JSON, including `poster_url` and
`trailer_embed_url`. Start Django and open `http://127.0.0.1:8000/api/v1/movies/238/`
for the read-only detail API response. The full auth/search/recommendation API is
scheduled for Phase 5 and frontend playback for Phase 6. The media checker checks
image headers and YouTube oEmbed.
Viewer region and provider availability can still affect playback.

Credentials live in ignored `backend/.env`: use `TMDB_READ_ACCESS_TOKEN` or
`TMDB_API_KEY`. Cache, manifests and verification JSON live in ignored `data/tmdb/`.

## Resume and refresh

Repeat the same import options to resume checkpointed selection and completed
batches. Upserts make a crash between database commit and checkpoint save safe to
retry. A PostgreSQL advisory lock prevents concurrent import commands.

`--new-snapshot` archives the old manifest and refreshes the selected catalog.
Existing rows are retained to preserve ratings/watchlists and later technique
references. `catalog_rank` records each movie's latest imported snapshot rank;
default queryset ordering uses stored vote average, vote count and TMDB ID.

Discovery is a changing paginated feed, not a frozen database snapshot. Results
are deduplicated by TMDB ID and sorted by captured rating, with vote count and ID
as deterministic tie-breakers. Details that no longer meet the filters are
explicit exclusions. The manifest records this evidence and does not claim an
exact ranking at a single instant.

Eight workers share an eight-request-per-second limit. Credits, keywords and videos
append to a single detail request. Cache lifetime defaults to 24 hours. Batches of
250 films are committed atomically with bulk relation writes. One upcoming batch
downloads while the current batch is stored, keeping memory use bounded.

## Verification completed

- First 20 authentic films imported with no exclusions.
- Repeated upserts preserved movie/genre/person/credit counts.
- Constraints reject duplicate ratings/watchlist items and scores outside 1–10.
- Profile creation is idempotent; 20 detail records serialize in three queries.
- Movie detail HTTP tests verify successful JSON, three queries, rejection of
  POST with 405, and missing-film 404 responses. A real local HTTP request also
  returned The Godfather's stored metadata and media URLs successfully.
- Verification uses authentic film data and rolls back all temporary writes;
  it does not create/drop a hosted test database.
- The Godfather poster returned HTTP 200 with `image/jpeg`; YouTube oEmbed returned
  HTTP 200 and an iframe for its TMDB-provided trailer key.
- Django system and migration consistency checks pass.
- The full import was interrupted after 1,100 completed records and successfully
  resumed from its saved selection and checkpoint.
- A later session resumed at 6,350 completed records and finished all remaining
  selected IDs. The final catalog audit passes.

## Optional user task: advance source collection

The user authorized preparing a separate collection task for another AI while
Phase 2 finishes. See [the complete scraping handoff prompt](scraping-handoff-prompt.md).
It defines source-specific JSON envelopes and record fields, validation, and output
paths under `data/raw/technique_sources/`. Per the user's refinement, collection
is limited to titles, readily available year/director clues, ranks and source URLs.
Optional metadata stays null; TMDB enrichment belongs to the later ingestion work.
TSPDT's official plain list was verified
to expose real ranked entries directly. No scraped records have been ingested;
the actual technique-source pipeline remains scheduled for approved Phase 7.

## Sources

- [Discovery filters](https://developer.themoviedb.org/reference/discover-movie)
- [Movie details and appended responses](https://developer.themoviedb.org/reference/movie-details)
- [Image URLs](https://developer.themoviedb.org/docs/image-basics)
- [Rate limiting](https://developer.themoviedb.org/docs/rate-limiting)

Phase 3 requires successful Phase 2 verification and explicit user approval.
