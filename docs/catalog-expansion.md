# Catalog expansion, reviews and trailer handoff

Verified on 17 September 2026. These additions were explicitly authorized by the
project owner alongside the original phased build.

## Catalog and provenance

The Supabase catalog contains **11,066 distinct TMDB movie IDs**. The expansion
added 678 records to the previous 10,388-film catalog; overlapping films were
updated in place. The original 9,999 catalog primary keys and ranks remain intact.
TMDB identity and source snapshot/rank constraints prevent duplicate records.

| Scraped source | Citations | Resolved movie citations |
| --- | ---: | ---: |
| Original Letterboxd Top 1000 | 1,000 | 997 |
| TSPDT Top 1000 | 1,000 | 993 |
| Letterboxd Top 250 Animated Films | 250 | 250 |
| Letterboxd Black and White list | 100 | 100 |

There are 1,656 distinct scraped-source movies across 2,350 citations. Nine TV
citations remain excluded and the combined Olympia entry remains unmatched,
as requested. Raw source payloads, hashes, ranks and identity evidence are retained
in the database and local project. A citation records source membership, not a
review or a claim that film analysis has been completed.

The new lists were fetched with `scripts/fetch_expansion_lists.py`, merged and
matched with `scripts/expand_catalog.py`; ambiguous matches were checked using
actual Letterboxd film-page TMDB links by `scripts/review_expansion_matches.py`.
Raw pages, plans, decisions and complete TMDB payloads are in `data/expansion/`
and `data/raw/technique_sources/`.

All 25 requested directors have verified released TMDB directing credits imported.
These can include shorts and documentaries represented as TMDB movies. The
director and country/martial-arts collections contain 1,077 distinct films,
including overlap with scraped lists. `data/expansion/curation.json` records every
director identity and collection member; it includes exactly 50 French, 50 Italian,
50 kung fu and 20 Shaw Brothers kung fu films.

Country selections require the matching origin country and original language;
French/Italian/kung fu selections require at least 200 votes. Kung fu membership
uses the exact TMDB keyword; Shaw membership also requires the verified production
company. Shaw films have no vote floor. Country/kung fu rankings sort TMDB rating
descending, then vote count descending and TMDB ID ascending. These are rankings
within the recorded TMDB criteria, not independent critical consensus lists.
TMDB-only collection membership never creates a scraped-source citation.

## Homepage and recommendations

Public editorial rows use scraped films or explicitly requested collection members,
with at least 200 TMDB votes. Existing rating/popularity ordering is retained.
Added sections: Drama, Horror, Black & White, Animation and International Cinema.
Black & White uses the actual supplied list; International Cinema means a known
non-English original language. Collection additions can appear in suitable sections;
there are no separate director/country/kung fu homepage rows. Personalized ranking
continues to use user preferences rather than preferential director weights.

The rebuilt content model covers all **11,066 films**. The rebuilt collaborative
model covers **8,656 films**, using **26,625,122 real MovieLens ratings** after
eligibility filtering. Unsupported films use the available content/popularity
components in hybrid recommendations; no synthetic collaborative ratings were added.
Both verified artifacts are active. `scripts/verify_expanded_hybrid.py` confirmed
all unseen catalog films remain eligible and unsupported collaborative scores are
absent, using an authentic MovieLens demo history. Evidence:
`data/expansion/hybrid-verification.json`.

Training sources remain under `training/content/` and `training/collaborative/`.
Exact code bundles, logs, checksums and run receipts remain inside the project:

- Content: `data/content/runs/20260917-065655-8a021b.*`
- Collaborative: `data/collaborative/runs/20260917-071032-f6a561.*`
- Previous model pointers: `data/expansion/model-baseline.json`
- Numerical verification: `data/content/verification.json` and
  `data/collaborative/verification.json`

The collaborative runner now uses a separate output folder/archive for every run
on a reused Studio. The earlier attempt stopped before fitting because the old
output folder existed; its failed receipt is retained. The successful run restored
the collaborative Studio to Running after artifact synchronization.

Held-out evaluation is distinct from the production refit: all-test RMSE 0.947655
versus baseline 0.949895; all-test MAE 0.721960 versus baseline 0.718815. Thus the
model improves RMSE slightly, but not all-test MAE. On the separate documented
deployment-style fold-in sample, RMSE is 0.792773 versus baseline 0.836945.

## Optional reviews

Everyone can read posted reviews. Signed-in users can save a star-only rating or
attach one editable review per film. Ratings display from 0.5 to 5 stars in 0.5
steps; the existing internal 1–10 recommendation scale remains compatible.

Review text is 10–3,000 characters, rendered as plain text. Ownership, CSRF and
database uniqueness are enforced. Links, control characters and same-user copied
text across different films are rejected. Review changes are limited to five per
minute and 20 per day, including relevant rating/delete operations; repeat identical
submissions are free no-ops. Quotas survive deletion. Moderators can hide reviews;
deleting/reposting cannot bypass moderation. Deleting review text preserves stars.

Verification: seven API cases, a concurrent real-database write check, and two
browser scenarios covering the homepage and review lifecycle passed. Evidence:
`data/expansion/review-api-verification.json`, `review-concurrency-verification.json`,
`browser-results.json`. API schema: `docs/openapi.yaml`.

## Official Letterboxd ratings

Movie detail pages embed the official TMDB-ID-based Letterboxd histogram alongside
the TMDB score, with a direct Letterboxd link. No IMDb ratings were added. Letterboxd
scores are not scraped into our database or used to reorder recommendations.

The integration follows [Letterboxd's published embed format](https://letterboxd.com/about/embed-our-ratings/).
The frontend production build passed. The automated browser check received a
**403 Cloudflare challenge**, whose SAMEORIGIN response prevents framing. Therefore
the live ratings display is **not verified in this environment**. The direct link
remains available; a normal-browser/deployed-site check is still required. No
proxying or challenge bypass was introduced. Evidence:
`data/expansion/letterboxd-browser-check.json`.

## 500 selected trailers

`data/phase8/trailer_manifest_500.csv` and `.json` contain exactly 500 unique films,
all cited by both original lists, with title/year/TMDB ID, source memberships and
ranks, trailer URL, exact filename and destination. TMDB-only additions are excluded.
The human-readable list is `data/phase8/TRAILER_DOWNLOAD_LIST.md`.

The user subsequently authorized a local downloader and one-film live test.
See [the downloader guide](../data/raw/technique_sources/webScraping/TRAILERS.md).
The Citizen Kane test succeeded and rerunning skipped the valid completed file.
The remaining batch is for the user to run. Trailer availability is not guaranteed
merely because TMDB provides a link.

Cinematography extraction is not implemented or run. Future shot/color/motion
measurements will describe the supplied trailers, not entire films.

## Read-only catalog audit

Run `.\.venv\Scripts\python.exe scripts/verify_expansion.py` from the project root.
It verifies source payload preservation, citation/flag correspondence, exact
collection memberships, directing credits, unique TMDB identities, original ranks,
homepage filters/order, all 500 manifest rows and complete content-model coverage.
The passing report is `data/expansion/catalog-verification.json`.
