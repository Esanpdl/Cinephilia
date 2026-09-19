# Phase 6: core frontend integration

## Status

Complete. The production build, eight unit checks, three public/error browser
scenarios, and the final account-flow browser scenario pass. Phase 7 source
ingestion has not started.

## Approved design

The user chose an editorial home with a featured-film hero, curated-looking rows,
a separate browse grid, and dedicated film pages. Criterion Channel supplied the
editorial reference; Be UI supplied motion references.

Kubrick, Hitchcock, Scorsese, Tarantino, Lynch, and Tarkovsky are **visual references
only**. Their influence is expressed through framing, shadow, restrained crimson,
warm ivory type, subtle grain, deliberate spacing, and slow reveals. No preference
for their films or directors is added to queries, catalog ordering, or recommendations.

The feature uses the first result in the existing rating-ordered catalog. Its
director credit and imagery belong to that actual movie. Public rows use rating
and popularity order; the signed-in row uses the existing hybrid API. No manually
chosen film, invented media, or new ranking weight is introduced.

## What was built

- React/TypeScript app with lazy routes, a shared responsive shell, local fonts,
  and Motion-based button/active-navigation interactions.
- Browse search, genre/year/order filters, URL-preserved pagination and empty/error states.
- Film pages with TMDB posters, backdrops, facts, cast, and click-to-load YouTube
  embeds using the stored TMDB trailer URL. Missing trailers receive a clear fallback.
- Django session registration/login/logout with CSRF bootstrap and token rotation.
  Local return paths are checked to prevent external redirects.
- Ratings from 1 to 10, rating removal, watchlist additions/removals, collection
  pages, personal recommendations, and profile editing.
- Keyboard focus styles, skip navigation, labeled forms, mobile navigation,
  reduced-motion support, image fallbacks, and retry controls.
- A hidden-window development launcher and scoped cleanup for browser-test accounts.

## Data and cache boundaries

The browser communicates only with Django REST. Supabase credentials, Django
secrets, and TMDB credentials remain on the backend; no private key is required
in the frontend. Session cookies travel with requests; CSRF tokens stay in memory.
A write retries once only when Django explicitly rejects its CSRF token. Network
failures do not trigger automatic write retries.

Catalog/detail queries have a five-minute freshness window, genres one hour.
Private keys include the account ID and are removed on logout or account changes.
A BroadcastChannel communicates session changes between tabs without sending
tokens. Rating/watchlist changes invalidate lists and recommendations. Saved UI
state is updated after successful server responses.

The existing Phase 5 recommendation models and weights are used unchanged. Rating
a film can influence results through those models; naming filmmakers as visual
references does not supply a preference signal.

## Integration fixes

Django's threaded development server retained enough connections to exhaust the
Supabase session pool during browser testing. With DEBUG enabled, connections now
close after each request. Production workers retain the configurable connection
lifetime. This follows Django's [development-server guidance on persistent
connections](https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections).
No database migration is needed.

Updating a saved rating originally cleared its success message during cache
synchronization. Draft synchronization and notice clearing now have separate
effects, so the saved/removed confirmation persists.

## Run and verify

From the project root, after installing frontend dependencies:

```powershell
& ./scripts/start_dev.ps1
```

Open http://127.0.0.1:5173/. Search for The Godfather, set year 1972, open its film
page, and activate the embedded trailer. Register or sign in to save a film and
rate it; check Your collection, For you, and Account.

The launcher retains existing services on ports 8000/5173. It writes logs/PIDs
to `data/phase6/`; Python changes require restarting its Django server because
the helper uses --noreload. Manual foreground startup and test commands are in
[the frontend guide](../frontend/README.md).

### Verification evidence

- Strict TypeScript and Vite production build pass. The initial JavaScript bundle
  is 432.78 kB (137.66 kB gzip); route components are split into separate chunks.
- Eight API-client/navigation unit checks pass: CSRF token rotation, controlled
  retry, network-write behavior, credential destination, session expiry,
  cancellation, and local return-path validation.
- Django system check passes with no issues.
- PostgreSQL connection verification passes with TLS active.
- The final account browser scenario passes: registration, watchlist addition and
  removal, rating save and removal, persisted collection, personalized feed with
  rated-film exclusion, profile editing, logout, protected-page redirect, and
  subsequent login. Its focused run completed in 129.59 seconds including setup
  and cleanup; this is test runtime, not application response latency.
- Desktop/mobile home and detail checks pass at 1440/390-pixel widths, including
  actual image loading, mobile menu behavior, and no horizontal overflow.
- Browse search/year filtering, missing-film/empty-search handling, simulated
  network failure/retry, and reduced-motion checks pass.
- The trailer test verifies that user interaction mounts the actual YouTube
  embed URL. It does not guarantee provider playback, regional availability, or
  future availability for every catalog trailer.
- Browser tests run against the configured Supabase development database. A
  uniquely named account is created and removed with its owned records/sessions.
  The test uses The Godfather as an existing, identifiable catalog film, not as
  a production selection preference.
- Screenshots: `data/phase6/screenshots/home-desktop.png`, `home-mobile.png`,
  `film-desktop.png`, and `film-mobile.png`. Full-page home capture waits for
  lazy-loaded posters before taking the image.

The first complete browser run after the database fix passed three public/error
scenarios and exposed the rating notice bug in the account scenario. Its receipt
is retained as `browser-results-before-rating-notice-fix.json`. The focused
account rerun writes `browser-results.json`. These are local integration checks,
not concurrent-load benchmarks or a cross-browser accessibility audit.

## Assumptions and next phase

The user-approved top-10,000 / at-least-200-votes catalog remains the basis of
public browsing, without a new rating cutoff or director preference. Profile
genre/student preferences are stored, while the core model uses actual ratings.

No new credentials are needed for Phase 6. Phase 7 requires the two user-scraped
source files at the paths in [the handoff prompt](scraping-handoff-prompt.md), or
the actual paths if they were saved elsewhere. Ingestion will preserve source
citations, resolve TMDB identities, deduplicate, and merge into the shared catalog.
The technique/student flag must come only from those source records.

Phase 7 requires the user's explicit go-ahead under the master brief.
