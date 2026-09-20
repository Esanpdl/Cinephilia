# Bug Fixes & Small Feature Requests Documentation

Record of changes made for the 7 issues specified in `cinephilia_bugfix_prompt.md`.

---

## 1. Star rating doesn't render after saving

- **Problem**: On the movie detail page (`/films/:id`), when a user saved or modified their personal rating, the numeric score updated in the text (e.g. `4.5 / 5 stars`), but the visual star icons did not fill in or reflect the saved score with half-star fidelity.
- **Root cause**: `FilmActions.tsx` only had a single static outline `<Star size={15} />` in `<legend>`, with no visual multi-star rating component rendering the user's saved rating.
- **Changes made**:
  - Created a reusable `StarRating` component in `frontend/src/components/ui.tsx` supporting full stars, half stars (via a clipped filled star overlaid on the empty star outline), and empty stars based on the rating value.
  - Added nearest half-star rounding (`Math.round(clamped * 2) / 2`) and boundary clamping `[0, max]` so continuous community ratings (e.g. 4.8 -> 5.0, 4.3 -> 4.5, 4.2 -> 4.0) and half-star personal ratings (4.5) map to exact visual stars without truncation or incorrect step jumps.
  - Integrated `StarRating` into `frontend/src/components/FilmActions.tsx` within `<legend className="rating-legend">`, passing `existing !== null ? existing / 2 : 0`.
  - Added CSS classes in `frontend/src/styles.css` (`.star-rating-display`, `.star-empty`, `.star-filled`, `.rating-legend`, `.rating-legend-left`, `.rating-legend-title`, `.rating-legend-score`).
  - Added unit test suite in `frontend/src/components/StarRating.test.tsx` testing 0, 0.5, 4.2, 4.3, 4.5, 4.8, 5.0 rating increments and boundary clamping.
- **Verification**: `frontend/src/components/StarRating.test.tsx` passes with 6/6 assertions; visual checks verify that a 4.5 rating renders 4 full stars and 1 half star.

---

## 2. Logo doesn't return to homepage

- **Problem**: Clicking the "CINEPHILIA." wordmark in the navbar was reported as not returning the user to the homepage (Discover feed).
- **Root cause**: The wordmark was wrapped in `<Link to="/" className="wordmark">`, but did not reset scroll position when clicked from the homepage or close the mobile navigation drawer when open.
- **Changes made**:
  - In `frontend/src/components/Layout.tsx`, added `onClick={() => { setMenu(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}` to the wordmark `<Link to="/">`.
- **Verification**: Clicking the wordmark navigates to `/`, scrolls smoothly to top, and closes the mobile navigation menu if open.

---

## 3. "Refresh selection" on the For You page does nothing

- **Problem**: On the `/for-you` page, clicking "Refresh selection" re-fetched the exact same 24 recommendations.
- **Root cause**: The backend `RecommendationQuerySerializer` and `RecommendationView` did not accept an offset or pagination parameter. The hybrid ranker computed deterministic scores for the candidate catalog, and `RecommendationView` always sliced `ranked[:limit]`. Furthermore, naive wrap-around without bounding additional items by the offset would produce duplicate recommendations when `limit - len(selected) > offset` (e.g. when total candidates are fewer than 24).
- **Changes made**:
  - In `backend/apps/recommendations/serializers.py`, added `offset = serializers.IntegerField(min_value=0, default=0, required=False)` to `RecommendationQuerySerializer`.
  - In `backend/apps/recommendations/views.py`, implemented offset slicing with duplicate-safe circular wrap-around: bounded additional wrap-around items by `min(limit - len(selected), offset)`, ensuring the wrapped slice `ranked[:additional]` never overlaps with `ranked[offset:]`.
  - In `frontend/src/api/queries.ts`, updated `recommendationsQuery(userId, offset = 0)` to pass `&offset=` in the query URL and key.
  - In `frontend/src/pages/ForYou.tsx`, added `const [offset, setOffset] = useState(0)` and wired the "Refresh selection" button to `setOffset(current => current + 24)`.
- **Verification**: Verified via `scripts/verify_bugfixes.py` that requesting offset 0 vs offset 6 returns distinct sets of recommended films and that circular wrap-around with fewer candidates than limit yields zero duplicate movie IDs.

---

## 4. No aggregate community star rating is shown

- **Problem**: On the movie detail page, only the external TMDB audience score was shown; there was no aggregate representation of Cinephilia users' own ratings.
- **Root cause**: `MovieDetailSerializer` lacked community rating aggregate fields, and `FilmDetail.tsx` had no UI element for community stars.
- **Changes made**:
  - In `backend/apps/movies/services/queries.py`, annotated `movie_details_queryset()` with `community_score_avg=Avg("user_ratings__score")` and `community_rating_count=Count("user_ratings__id", distinct=True)`.
  - In `backend/apps/movies/serializers.py`, added `community_rating` and `community_rating_count` to `MovieDetailSerializer`. Community score (1-10) is converted to stars (0.5-5.0) and rounded to 1 decimal place. When unrated, `community_rating` is `None` and count is `0`.
  - In `frontend/src/api/types.ts`, added `community_rating: number | null` and `community_rating_count: number` to `MovieDetail`.
  - In `frontend/src/pages/FilmDetail.tsx`, added `.detail-ratings-row` containing `.tmdb-rating` and `.community-rating`, showing star icons (`<StarRating value={film.community_rating ?? 0} size={18} />`), the average score `/5` (or `—/5`), and label "Cinephilia community" with the rating count or "No ratings yet".
  - In `frontend/src/components/FilmActions.tsx`, added `void cache.invalidateQueries({ queryKey: ['movie', movieId] })` in `refresh()` so saving or deleting a rating instantly refreshes the community rating.
  - Added matching styles in `frontend/src/styles.css`.
- **Verification**: Verified via `scripts/verify_bugfixes.py` that empty movies report `community_rating=None`, and ratings dynamically compute the correct star average and count.

---

## 5. Letterboxd rating embed is too large

- **Problem**: The Letterboxd histogram embed iframe took up excessive vertical space (300px height by 440px width), creating a large empty block on film pages.
- **Root cause**: Hardcoded `height="300"` on the iframe and `max-width: 440px` in `frontend/src/styles.css`.
- **Changes made**:
  - In `frontend/src/pages/FilmDetail.tsx`, changed iframe `height="300"` to `height="100"`.
  - In `frontend/src/styles.css`, updated `.letterboxd-rating` to `max-width: 280px; margin: 18px 0;` and `.letterboxd-rating iframe` to `height: 100px; border-radius: 3px;`.
- **Verification**: Verified that the Letterboxd box is now compact, responsive, and does not dominate the viewport on either desktop or mobile.

---

## 6. Fully remove "Avatar Aang: The Last Airbender" from the app

- **Problem**: "Avatar Aang: The Last Airbender" (TMDB 980431) was in the database and occupied top spots on the homepage hero, Essential Viewing, and Animation rows due to an inflated vote average (9.138).
- **Root cause**: TMDB 980431 was imported during catalog expansion and linked to a `TechniqueSourceCitation` (id 2228, status `resolved`).
- **Changes made**:
  - Created management command `backend/apps/movies/management/commands/remove_avatar_aang.py`.
  - Updated citation 2228 to `status="excluded"` and `movie=None` in compliance with model constraints.
  - Deleted `Movie` record `980431`.
  - Flushed Django cache (`cache.clear()`).
- **Verification**:
  - `Movie.objects.filter(tmdb_id=980431).exists()` is `False`.
  - Searches for "Avatar Aang" and "Airbender" return zero results.
  - Homepage hero slot automatically fell through to the next eligible film: *The Shawshank Redemption* (TMDB 278).
  - Essential Viewing carousel displays a full 6-film lineup starting with *The Shawshank Redemption*, *The Godfather*, and *Macario*.
  - Animation theme carousel displays a full 6-film lineup starting with *Spirited Away*, *Your Name.*, and *Grave of the Fireflies*.
  - No gaps or null errors occur in any slot.

---

## 7. Rename "Film Students" to "Film Analysis" in the navbar

- **Problem**: The navbar link was labeled "Film Students", which needed to be renamed to "Film Analysis".
- **Root cause**: Label string in `Layout.tsx`.
- **Changes made**:
  - In `frontend/src/components/Layout.tsx`, updated `links` array: `{ to: '/students', label: 'Film Analysis' }`. Route `/students` and all student views were preserved without changes.
- **Verification**: Verified `Layout.tsx` contains `label: 'Film Analysis'` and no longer contains `label: 'Film Students'`.

---

## 8. Score-Weighted Recommendation Refresh & Tonight's Feature Random Selection

- **Documentation**: See full details in `docs/recommendations_refresh_and_featured.md`.
- **Key Enhancements**:
  - **Recommendation Refresh (`/for-you`)**: Replaced rigid offset pagination with score-weighted sampling (Efraimidis & Spirakis A-Res) from the top-tier candidate pool (top 72 highest-scoring films computed by `HybridService.rank()`), returning 24 distinct recommendations with zero duplicates and fresh variety on every refresh. Initial load without `refresh_seed` returns top recommendations directly.
  - **Tonight's Feature (Homepage Hero)**: Created `GET /api/v1/movies/featured/` to randomly select a movie from the 500 films in the film analysis (`/students`) collection (`TrailerAnalysis`, all with `is_technique_source=True`) on each refresh.
