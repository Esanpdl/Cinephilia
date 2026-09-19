# Cinephilia frontend

React, TypeScript, Vite, React Router, TanStack Query, and Motion. All film facts and
media URLs come from the existing Django API. No private keys belong in this app.

## Run

Use Node 22.12+ and the configured Django backend on port 8000.

```powershell
# From frontend/
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173/. Alternatively, from the project root run
`& ./scripts/start_dev.ps1` to start missing backend/frontend services in hidden
windows. The helper leaves already occupied ports alone; check the logs in
`data/phase6/` if a different app is using either port. It starts Django with
`--noreload`, so restart that server after changing Python code.

The default Vite proxy sends `/api` to `http://127.0.0.1:8000`. Keep
`VITE_API_ORIGIN` empty for this setup; no frontend environment file is required.
If explicitly using a separate API origin, configure Django's allowed CORS/CSRF
origins and use the same hostname. Production hosting must serve the SPA with a
fallback to index.html and proxy /api to Django, or supply the API origin at build
time. Vite's development proxy is not part of the production build.

## Routes

| URL | Page |
| --- | --- |
| / | Featured film and editorial rows |
| /browse | Shared title/director/actor search, genre, release-year range, order and pagination |
| /films/:tmdbId | Film facts, embedded media, rating and watchlist |
| /register and /login | Django account creation and session sign-in |
| /for-you | Signed-in recommendation feed |
| /collection | Watchlist and ratings |
| /account | Profile and sign-out |
| /students | Selected 500-film study collection |
| /students/films/:tmdbId | Trailer palettes, study cards, representative frames and text masks |
| /students/cards, /students/compare, /students/explore, /students/quiz | Visual learning tools |
| /students/contribute, /students/moderation | Contributions and staff review |

The filmmaker references influence visual presentation only. The home feature is
the first film in the existing rating-ordered catalog; the other public row uses
existing popularity order. Signed-in recommendations come from the Phase 5 engine.

## Checks

```powershell
npm.cmd test
npm.cmd run build
# Install Chromium if a compatible browser is not already available:
npx.cmd playwright install chromium
# Both development servers must be running:
npm.cmd run test:e2e
```

For an existing Chromium binary, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to its
absolute path before running browser tests. Tests use the real configured
development database and TMDB media, so they require network access. The account
test creates a uniquely named temporary account and removes only that account,
its owned records, and its sessions in a finally block. Traces are disabled.
If the entire process is forcibly terminated, use the scoped cleanup helper with
the exact test username: `python scripts/cleanup_phase6_test_account.py USERNAME`
from the project root with the project venv.

Browser results and desktop/mobile screenshots are retained locally in
`data/phase6/`. See [the Phase 6 report](../docs/phase-6.md) for verified coverage.

For the student section, run `npm.cmd run test:e2e -- --config playwright.students.config.ts`.
Its evidence is retained in `data/phase8/`; see the
[film-student guide](../docs/film-student-guide.md) for extraction, source review
and current verification receipts.
