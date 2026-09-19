# Architecture and phase boundaries

```text
React (Phase 6) → /api/v1/ REST + session/CSRF → Django → Supabase PostgreSQL
                                                ↓
                                      Domain service modules
                                                ↓
                                  TMDB / trained model artifacts
```

| Folder / Django app | Ownership |
| --- | --- |
| `backend/config` | Settings, middleware, root URLs, WSGI/ASGI |
| `backend/apps/users` | User profile and session authentication APIs |
| `backend/apps/movies` | Canonical film catalog and standalone TMDB service |
| `backend/apps/ratings` | Ratings and watchlists |
| `backend/apps/recommendations` | Swappable content, collaborative and hybrid services |
| `backend/apps/cinematography` | Technique sources, CV vectors, tagging and learning features |
| `backend/apps/admin_panel` | Moderation REST interface; separate from built-in Django admin |
| `frontend` | React product interface, typed REST client, session context and query cache |
| `training` | Retained Lightning AI training source and teacher evidence guide |
| `data/raw` | User-supplied source data and trailers; ignored |
| `artifacts` | Trained model files; ignored |
| `data/content` | Authentic catalog snapshots, content indexes, active pointer and Lightning receipts; ignored |

Each domain has its own models, migrations, service package and URL namespace.
Serializers and views are added alongside the feature they serve. Views should
delegate work to services. Recommendation engines will have swappable interfaces;
cinematography vectors must remain independent from core recommendation artifacts.
Phase 2 adds catalog, rating/watchlist and profile models with a standalone TMDB
service, resumable bulk importer and a read-only movie detail API for media
verification. The full core API remains scheduled for Phase 5.

Phase 3 exports catalog metadata in one read-only repeatable-read transaction,
then fits five TF-IDF blocks on a Lightning CPU Studio. The artifact stores a
sparse normalized feature matrix and the top 100 cosine neighbors per film.
`ContentSimilarity` defines the internal ranking/scoring contract;
`get_content_service()` selects the implementation through `CONTENT_SERVICE_CLASS`.
Inference reads a verified JSON/NPZ artifact without database or TMDB calls.
An atomic pointer activates a new immutable artifact, and each process caches its
loaded service until that pointer changes. No recommendation HTTP routes exist
in this phase. Cinematography and collaborative filtering remain separate.

Phase 4 adds an independent collaborative service and artifact pointer. Offline
MovieLens ratings are matched to existing TMDB movie IDs and train biased SVD on
Lightning. The production artifact contains movie factors and biases; site user
preferences are inferred from their own `Rating` rows. MovieLens user IDs never
become Django users or model indices for site accounts. Unsupported movies or
insufficient history return an explicit missing collaborative signal for Phase 5.

Django's built-in User is the auth identity, extended through a Profile in Phase 2.
Supabase Auth is not used. Only the backend connects to PostgreSQL.
Connections require TLS and use a short connection timeout and bounded reuse.
Django tables live in the `cinephilia` schema, outside Supabase's default public
Data API schema. `prepare_database` creates it before migrations; the connection
search path selects it explicitly.
The session pooler is selected for Windows/IPv4 compatibility; transaction mode
on port 6543 is rejected to avoid session-state and migration surprises.

Phase 5 composes the existing model services in an independent hybrid module.
It reads the signed-in user's own rating/watchlist rows, supplies explicit
missing-coverage fallbacks, and hydrates only the returned catalog movies.
Relative content, collaborative and log-normalized TMDB popularity scores use
configurable weights. The core APIs expose CSRF-protected session auth, catalog
search/detail, private ratings/watchlists and recommendations, with OpenAPI and
locally served Swagger/ReDoc documentation. No Phase 5 model fit or DB migration
is required. See [the API and scoring contract](phase-5.md).

Phase 6 adds the React application with route-level code splitting, a same-origin
Vite development proxy, and CSRF-aware session requests. Public catalog queries
are cached briefly; private cache keys include the account ID and are cleared on
logout/account changes. Rating and watchlist changes invalidate the relevant lists
and recommendation feed. The presentation uses cinematic visual references without
adding director preferences to catalog selection or recommendation scoring.

Development database connections close after each request (`DEBUG=True`), because
Django's threaded development server otherwise exhausts the small Supabase session
pool. Production connection lifetime remains configurable. No schema change is
needed. See [Phase 6](phase-6.md) for browser checks and frontend boundaries.

Phase 7 stores immutable raw source snapshots and ranked citations in the
cinematography app, resolving them into the shared Movie catalog by unique TMDB
ID. Source flags derive only from resolved citations. Reviewed TV and unmatched
entries preserve provenance without movie links. Full TMDB metadata is refreshed
through the existing catalog service under its shared import lock; trained model
artifacts are unchanged. The separately requested catalog search now prioritizes
title, director and cast matches using SQL EXISTS, without duplicate result rows.
See [Phase 7](phase-7.md) for evidence, commands and limitations.

The core backend was verified before Phase 6 frontend work. The user's PostgreSQL
and UI instructions override the corresponding original prompt choices.

The film-student section now uses a separate `TrailerAnalysis` per selected film,
with source digests, text-masked color measurements and frame evidence. Its
palette histogram comparisons do not enter the core recommendation score.
Accepted source reviews bind exclusions to the video checksum and review recipe.
The extraction runner applies them before import; the importer withholds stale
approvals and unapplied exclusions. Source kinds distinguish trailers, promos,
featurettes and scene excerpts without claiming whole-film measurements.
All 500 selected identities remain visible; unavailable or unreviewed evidence
is excluded from public frames, study cards, comparisons, charts and quizzes.
`TechniqueSubmission` supports moderated contributions across the full catalog.
The React student routes consume the `/api/v1/cinematography/` API. See the
[film-student guide](film-student-guide.md) for the current measurement scope,
source review workflow and verification receipts. Subsequent phase work remains
separate from resuming this section.
