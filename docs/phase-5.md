# Phase 5: hybrid recommendations and core API

## Status

Complete. All 18 Phase 5 tests pass, plus seven content and eight collaborative
regression tests. The OpenAPI schema validates with zero warnings/errors; Django
checks, migration consistency and dependency checks pass. Phase 6 product UI and
Phase 7 scraped-source ingestion have not started.

## Verified results

- 14 documented API paths. Swagger and all four local Swagger assets returned HTTP
  200 in the local HTTP smoke check.
- Login/registration CSRF protection, token rotation, logout, password validation,
  privilege isolation and login throttling pass.
- CORS allowlists, private response headers, profile validation, rating/watchlist
  ownership and idempotency pass. The Swagger interceptor also passed JavaScript
  execution checks for token rotation and preventing cross-origin token leakage.
- Search uses three database queries for both one-item and 20-item pages.
- A real six-rating MovieLens demo profile enables both personalized components.
  The authenticated 20-result recommendation request uses six database queries,
  including session/account loading. Rating/watchlist changes affect the next
  request; rated and excluded watchlisted films do not reappear.
- Pure hybrid ranking averaged **536.16 ms** over three warmed calls with supplied
  history/catalog and used zero database queries. The measured complete
  authenticated Supabase-backed request took **3.44 seconds**. These are local
  smoke timings, not concurrent-load or recommendation-quality benchmarks.
- Database user/rating/watchlist/movie counts were unchanged after rollback.
- Evidence: `data/phase5/verification.json` and
  `data/phase5/http-verification.json`. No global model was retrained.

## API routes

All identifiers in movie routes are **TMDB IDs**, not internal database row IDs.
The base path is `/api/v1/`. Only catalog browsing and CSRF/login/registration
are public. Other routes use the signed-in Django account; clients cannot choose
another account by sending a user ID.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `users/csrf/` | Set CSRF cookie and return a token |
| POST | `users/register/` | Validate password, create account/profile, sign in |
| POST | `users/login/` | Sign in with username and password |
| POST | `users/logout/` | End the session |
| GET | `users/me/` | Current account and profile |
| GET, PATCH | `users/me/profile/` | Display name, bio, student preference, favorite genre IDs |
| GET | `movies/` | Paginated catalog/search |
| GET | `movies/genres/` | All imported genres |
| GET | `movies/{tmdb_id}/` | Details, cast/directors, poster and trailer embed URLs |
| GET | `ratings/` | Your paginated ratings |
| GET, PUT, DELETE | `ratings/{tmdb_id}/` | Read, create/replace or remove your rating |
| GET | `ratings/watchlist/` | Your paginated watchlist |
| GET, PUT, DELETE | `ratings/watchlist/{tmdb_id}/` | Read, add or remove your watchlist entry |
| GET | `recommendations/` | Your hybrid recommendations |

Documentation is separate from product UI:

- Swagger: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`
- OpenAPI: `/api/schema/` and the checked-in `docs/openapi.yaml`.
- Swagger/ReDoc assets are pinned, locally served sidecar files; no CDN is needed.

### Verify in Swagger

Start Django from the Cinephilia folder:

```powershell
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

1. Open Swagger and execute `GET users/csrf/`.
2. Execute `POST users/register/` with your chosen username and strong password,
   or `POST users/login/` for an existing account.
3. Execute `GET users/me/` to confirm the session. No token authorization dialog
   is needed: the browser sends the HttpOnly session cookie.
4. Search `GET movies/?q=Godfather`, then inspect `GET movies/238/`.
5. Execute `PUT ratings/238/` with `{"score": 9}`. Add other genuine preferences
   to enable collaborative predictions after three covered movies.
6. Execute `GET recommendations/`; inspect component scores and effective weights.
7. Add/remove a watchlist item, then rerun recommendations.
8. Execute `POST users/logout/`.

The Swagger request interceptor reads the current CSRF cookie for each unsafe
request, including after login rotates it. External clients should retain cookies
and send `X-CSRFToken` with POST/PUT/PATCH/DELETE. The CSRF/login/register responses
include a token. React will use `credentials: "include"`; keep the same hostname
on both ports and configure the explicit CORS/CSRF origin allowlists.

### Inputs and behavior

- Search: `q` (title/original title, director or actor, up to 200 characters), `genre`
  (TMDB genre ID), `year_from`, `year_to`, `ordering=rating|popularity|newest|title`,
  `page`, `page_size`. As extended in Phase 7, results prioritize title, director,
  then actor matches; ordering applies within each group. Inclusive year ranges
  support 1895 through the current year. Legacy exact `year` remains supported,
  but cannot be combined with range parameters. See [Phase 7](phase-7.md).
- Lists default to 20 entries, maximum 60. Invalid bounds produce 400; an absent
  page beyond the end produces 404. Catalog ordering has stable TMDB-ID tie breaks.
- Recommendations: `limit` defaults to 20, maximum 60; `exclude_watchlist` defaults
  to true. Rated films are always excluded regardless of score.
- Rating PUT accepts an integer score from 1 through 10. PUT creates (201) or
  updates (200) one row under the existing database uniqueness constraint.
- Watchlist PUT has no request body and creates (201) or reuses (200) one entry.
- DELETE returns 204 even if your entry is already absent, provided the film exists.
  It never removes another account's entry. Missing movies/owned GET entries are 404.
- Registration accepts username/password, optional email/display name/student
  preference. Email is optional, unverified, and is not the login identity.
- Biography limit is 2,000 characters; favorite genre IDs must exist in the catalog.
  These profile preferences are stored; recommendations currently use actual ratings.
- Anonymous private requests and rejected CSRF checks return 403. Invalid inputs or
  credentials return 400. Login is throttled to 10/minute, registration to 5/hour
  per client identity. The default throttle cache is per process.
- Auth, rating/watchlist and recommendation responses are private and non-cacheable.
- Missing media stays null/empty according to the TMDB data. No trailer is invented
  or fetched on demand by these endpoints.

## Hybrid composition

`services/hybrid/engine.py` combines replaceable content and collaborative services.
It does not train, update or merge their saved artifacts.

Defaults, configurable through environment variables:

| Setting | Default |
| --- | ---: |
| HYBRID_CONTENT_WEIGHT | 0.45 |
| HYBRID_COLLABORATIVE_WEIGHT | 0.40 |
| HYBRID_POPULARITY_WEIGHT | 0.15 |
| HYBRID_MIN_LIKED_RATING | 7 |
| HYBRID_MAX_CONTENT_SEEDS | 20 |
| HYBRID_CATALOG_CACHE_SECONDS | 300 |

Weights are normalized and must be finite/nonnegative, with a positive popularity
weight to guarantee fallback. Django's system checks reject invalid configuration.
A zero content or collaborative weight disables that component.

1. **Content:** choose up to 20 indexed films rated at least 7, strongest ratings
   first and most recent first for ties. Weight each seed by
   `rating - minimum_liked_rating + 1`. Average its cosine similarities, then
   divide by the largest average among the remaining covered candidates. This is
   a relative score for this profile/candidate set; a zero similarity remains zero.
   Unindexed candidates or no positive seeds produce a missing content signal.
2. **Collaborative:** infer a user vector from the account's actual rating history
   using the Phase 4 fixed movie factors. Its normalized prediction is
   `(prediction_on_0.5_to_5_scale - 0.5) / 4.5`. Fewer than three covered ratings
   or an uncovered candidate produces a missing signal.
3. **Popularity:** use `log(1 + TMDB popularity)` divided by the largest such value
   in the cached catalog. An all-zero catalog yields zero scores and ID tie breaks.
4. For each film, redistribute weights proportionally over its available signals
   and sum the weighted scores. Missing signals are returned as null; their effective
   weight is zero. A measured zero similarity is still an available signal.
5. Sort score descending with TMDB ID as a deterministic tie break.

New users therefore receive popularity results. Users with liked films gain content
personalization; sufficient covered ratings enable collaborative personalization.
Missing model artifacts are logged and exposed through availability flags while the
other components continue. Film-student flags and future CV vectors never affect
this core ranking.

These defaults are **chosen weights, not learned/calibrated parameters**. Scores
are ranking signals, not probabilities or predicted TMDB ratings. Phase 4's RMSE
evaluated collaborative predictions; it is not a quality benchmark for this hybrid.
Content's relative scale changes when the eligible set changes.

## Efficiency and storage

- Full catalog detail uses prefetches; search uses count + page + genre queries.
- Catalog ID/popularity data is cached for five minutes per process. A catalog
  change becomes visible to the recommender after expiry or a process restart.
- User history and watchlist are read fresh each request, so rating/watchlist writes
  affect the next recommendation immediately. No cross-user recommendation cache exists.
- Only returned recommendation movies and genres are hydrated. Query counts do not
  grow with page size. Existing indexes support user lists, unique upserts, genre
  relations, years and rating ordering. Substring title search scans this 9,999-film
  catalog; a trigram index can be added if later profiling warrants it.
- Both verified model instances are cached per process. Their existing atomic
  artifact pointers still control reloads.
- No TMDB calls or global training happen in API requests. All movies stay in the
  canonical Supabase catalog; MovieLens identities remain offline.
- Phase 5 requires no schema migration, new credentials or Lightning training.
- All training code and exact historical bundles from Phases 3/4 remain in the
  project. Phase 5 adds only a read-only coverage method to the content interface.

## Automated verification

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase5.py
.\.venv\Scripts\python.exe backend/manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pip check
```

The verification script uses authentic imported movies and the saved real MovieLens
demo history. Numerical scoring fixtures are isolated from movie facts/training.
Temporary test accounts and interactions are always rolled back in Supabase, with
before/after counts checked. It does not create/drop a hosted test database.
Node.js executes the Swagger interceptor check; it requires no npm packages.
Results are saved to ignored `data/phase5/verification.json`.

## Next phase

The master brief requires explicit approval and frontend-specific design input
before Phase 6. Be UI motion components and Criterion Channel remain the requested
references. Scraped-source matching/storage is reserved for Phase 7; the
film-student interface is Phase 9.

## Implementation references

- [DRF session authentication and anonymous-login CSRF requirements](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication).
- [drf-spectacular installation and local UI assets](https://drf-spectacular.readthedocs.io/en/stable/readme.html).
