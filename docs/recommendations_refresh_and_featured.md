# Recommendation Refresh & Tonight's Feature Random Selection Documentation

Documentation for the two core improvements to recommendation refresh and homepage hero featured film selection.

---

## 1. Score-Weighted Refresh in the "For You" Section (`/for-you`)

### Problem
Previously, refreshing recommendations on the `/for-you` page used rigid offset pagination (`offset += 24`). As the offset increased, the user was shown lower-scoring, worse, or irrelevant movies that did not properly fit their taste profile.

### Solution
Instead of paginating into worse catalog movies, recommendation refresh now samples from a **top-tier candidate pool** (top 72 highest scoring movies computed by `HybridService.rank()`):
1. **Candidate Pool**: When a `refresh_seed` parameter is supplied, the top 72 highest-scoring movies (3x batch size of 24) are extracted from the hybrid ranker.
2. **Score-Weighted Sampling Without Replacement**: A weighted reservoir sampling algorithm (Efraimidis and Spirakis A-Res algorithm) is performed using the user ID and `refresh_seed`:
   - For each candidate in the top-tier pool, a key $k_i = u_i^{1/w_i}$ is calculated (in log space: $\ln(k_i) = \frac{\ln(u_i)}{w_i}$), where $w_i = \max(\text{score}_i, 10^{-6})$ and $u_i \sim U(10^{-7}, 1.0)$.
   - The top 24 entries with the highest keys are chosen, guaranteeing zero duplicates.
   - The selected 24 movies are presented sorted by score descending, ensuring the strongest recommendations appear first.
3. **Initial Load**: On initial load without `refresh_seed`, the top recommendations are returned directly (`ranked[:limit]`), preserving deterministic top ranking.
4. **Variety**: Each click of "Refresh selection" on the frontend generates a new timestamp seed (`Date.now().toString()`), producing a fresh variety of high-fit recommendations without ever dropping into irrelevant catalog tiers.

### Files Changed
- `backend/apps/recommendations/serializers.py`: Added `refresh_seed = serializers.CharField(max_length=128, required=False, allow_blank=True)` and updated `limit` max to 100 in `RecommendationQuerySerializer`.
- `backend/apps/recommendations/views.py`: Implemented top-tier candidate pool (top 72) identification and Efraimidis-Spirakis score-weighted sampling without replacement when `refresh_seed` is provided. Preserved backward-compatible offset logic when omitted.
- `frontend/src/api/queries.ts`: Updated `recommendationsQuery(userId, refreshSeed, offset)` to pass `refresh_seed`.
- `frontend/src/pages/ForYou.tsx`: Updated state from `offset` to `refreshSeed`. On click of "Refresh selection", `setRefreshSeed(String(Date.now()))` is triggered.

---

## 2. "Tonight's Feature" Random Selection from Film Analysis Collection

### Problem
Previously, "Tonight's feature" (the homepage hero on the Discover feed) deterministically selected the #1 highest-rated movie from `HIGHLIGHTS` (`moviesQuery({ page_size: 6, ordering: 'rating', homepage: 'true' })`), which always displayed the exact same film on every visit and refresh.

### Solution
"Tonight's feature" is now randomly selected on each refresh from the 500 movies selected for the Film Analysis (`/students`) section (the curated technique sources catalog with `TrailerAnalysis` records, all having `is_technique_source=True`):
1. **Dedicated Endpoint**: Created `GET /api/v1/movies/featured/` (`FeaturedMovieView` in `apps.movies.views`), routed in `backend/apps/movies/urls.py`.
2. **Curated 500 Pool**: The view queries candidate IDs from `TrailerAnalysis.objects.values_list("movie__tmdb_id", flat=True)` (with fallback to `Movie` technique sources).
3. **Random Selection on Refresh**:
   - For standard requests, `secrets.choice(candidate_ids)` selects a random film from the 500 film analysis collection.
   - For deterministic testing, an optional `?seed=` query parameter is supported and validated via `FeaturedMovieQuerySerializer` (max 128 characters).
   - Slices and queries use explicit ordering (`order_by("selection_rank")` for `TrailerAnalysis`, and `order_by("catalog_rank", "tmdb_id")` for fallbacks) to ensure deterministic seeded selection across all environments.
   - Response includes `Cache-Control: no-cache, no-store, must-revalidate, max-age=0` and `Pragma: no-cache` headers so browsers and proxies do not cache the featured movie.
4. **Single-Query Detail Fetch**: The selected movie is loaded via `get_object_or_404(movie_details_queryset(), tmdb_id=chosen_id)` and serialized with `MovieDetailSerializer`, returning the full detail object (including `backdrop_url`, `directors`, `title`, `overview`, `genres`, `runtime`, `trailer_embed_url`, and `community_rating`) in a single network request.
5. **Frontend Integration**:
   - In `frontend/src/api/featured.ts`, updated `useFeaturedFilm()` and added `featuredMovieQuery()` calling `/api/v1/movies/featured/` with `staleTime: 0, gcTime: 0`.
   - On page refresh or mount, a freshly randomized film from the 500 film analysis collection is fetched and rendered in the hero.

### Files Changed
- `backend/apps/movies/serializers.py`: Added `FeaturedMovieQuerySerializer`.
- `backend/apps/movies/views.py`: Added `FeaturedMovieView` with `FeaturedMovieQuerySerializer` parameter validation and schema documentation, deterministic ordering, and `get_object_or_404`.
- `backend/apps/movies/urls.py`: Added `path("featured/", FeaturedMovieView.as_view(), name="featured")`.
- `frontend/src/api/featured.ts`: Updated `useFeaturedFilm()` to query `/api/v1/movies/featured/`.
- `frontend/src/api/client.test.ts`: Added tests for `featuredMovieQuery` and `recommendationsQuery`.
- `backend/apps/movies/tests.py`: Added tests for `FeaturedMovieQuerySerializer`.
- `backend/apps/recommendations/tests.py`: Added tests for `RecommendationQuerySerializer` with `refresh_seed` and `limit`.
- `scripts/verify_bugfixes.py`: Added `test_tonights_feature_random_selection()` with seed validation, and extended `test_issue_3_recommendations_refresh()`.
- `docs/openapi.yaml`: Updated OpenAPI schema with `/api/v1/movies/featured/` (including `seed` parameter) and `refresh_seed` parameter.

