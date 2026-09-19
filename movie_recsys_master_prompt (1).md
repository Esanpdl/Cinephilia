# Master Build Prompt: Hybrid Movie Recommendation & Film-Student Cinematography Platform

## PROJECT OVERVIEW

You are acting as the lead developer for a college capstone project: a web-based hybrid movie recommendation platform (content-based + collaborative filtering, backed by TMDB data) with a unique differentiator — a cinematography/editing-technique learning layer aimed at film students, built from computer-vision analysis of a curated subset of films plus a crowdsourced tagging system across the full catalog.

Read this entire prompt before writing any code. You will build this project in **10 sequential phases**, defined at the bottom of this document. Follow the global rules below at all times, across every phase, with no exceptions.

---

## GLOBAL RULES

1. **Ask before advancing.** At the end of every phase, stop, deliver a progress report in the format specified below, and explicitly ask for permission before starting the next phase. Do not bundle multiple phases into one response, and do not begin a new phase's work inside the same response where a prior phase was just completed.

2. **Core before extras.** Phases 1–6 build the core recommendation system end-to-end (backend, models, and its frontend). Nothing from Phase 7 onward starts until Phase 6 is confirmed working and I've explicitly approved moving on.

3. **Modular architecture.** Every feature lives in its own Django app / service module / React component tree. No feature's code should be tangled into another's — I should be able to disable, replace, or debug one feature without touching the others. Use clear interfaces (service classes, serializers, API endpoints) between modules. Favor composition over tightly coupled logic.

4. **Backend and frontend are fully separated.** All communication happens through documented REST API endpoints (Django REST Framework). No server-rendered templates mixing logic and UI. The backend must be completely functional and testable (e.g. via Swagger/Postman) before any frontend work begins on that feature.

5. **Frontend requires my input first.** Before starting *any* frontend phase or any new frontend section, stop and ask me for my design/layout ideas for that specific part before writing UI code. Do not assume a design or proceed on placeholder styling I haven't approved.

6. **Debugging protocol.** I may ask you to debug at any point, in any phase — be ready for this at all times. When I report an issue:
   - If I haven't given an error message, reproduction steps, or the relevant module, ask for whichever of those is missing before guessing.
   - Isolate the issue to its specific module — do not touch unrelated modules while investigating.
   - Explain the likely root cause before applying a fix, so I understand what broke and why.
   - After fixing, briefly note what else (if anything) could be affected by the change, and confirm you checked it.
   - Keep changes minimal and scoped to the actual bug — don't refactor unrelated code while fixing something else.

7. **Model training happens on Lightning AI.** When a phase requires training (embeddings, collaborative filtering model, any CV model), ask me explicitly for my Lightning AI credentials when you need them — don't assume you already have them. Note that Lightning AI authentication requires **two values together**, not a single key: `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY`. Ask for both by name. Use the credentials to run the training job yourself via the Lightning AI API/SDK rather than asking me to manually train it.
   - **Training fallback protocol:** if training fails or stalls because Lightning AI credits are exhausted, stop and tell me clearly. I will either (a) provide new account credentials to continue, or (b) train it myself locally or on another device. In case (b), package everything I need: the complete training script, the exact dataset (or precise, authentic instructions for obtaining it — never a placeholder or synthetic substitute), dependency requirements, and clear instructions for running it and where to place the resulting model artifact so your integration code picks it up correctly.
   - If any training-related step genuinely requires manual action from me that the API can't do (reviewing metrics, approving a config, etc.), stop and tell me exactly what to do.

8. **Code must be optimized**, not just functional: sensible DB indexing, query optimization (avoid N+1 queries), caching where it meaningfully helps (e.g. similarity matrices, TMDB responses), and no redundant API calls. Don't over-engineer beyond what the project needs, but don't leave obvious inefficiencies either.

9. **TMDB is the source of movie data**, including posters and trailers. Posters and trailers must be **embedded directly in the UI** (poster via TMDB image CDN URLs, trailer via embedded YouTube player using the trailer key from TMDB's videos endpoint) — not just linked out.

10. **I am doing the web scraping myself**, not you. Whenever scraped data is needed, tell me precisely: (a) what fields to scrape, (b) suggested source structure, (c) exactly what file format and folder path to save it to, so your ingestion scripts can pick it up without guessing.

11. **I am fetching trailer files myself**, not you. Do not attempt to auto-download trailers. Tell me exactly what trailer files/formats you need and what folder path to place them in, then wait for me to supply them before running any analysis that depends on them.

12. **Never fabricate or guess data.** Not movie facts, not scraped fields, not dataset contents, not API responses, not benchmark numbers. If a source can't be scraped as expected, if a page structure doesn't match what was assumed, or if you're missing information needed to proceed authentically, stop and ask rather than inventing plausible-looking data or silently working around it.

---

## TECH STACK

- **Backend:** Django + Django REST Framework
- **Database:** MySQL
- **Auth:** Django session authentication
- **Frontend:** React (design/UX to be provided by me per phase)
- **ML training:** Lightning AI (credentials — `LIGHTNING_USER_ID` + `LIGHTNING_API_KEY` — provided when needed)
- **External data:** TMDB API (movies, posters, trailers); user-provided scraped data for the film-student technique dataset

---

## MODEL EFFORT NOTE

For most phases, default thinking/effort settings are fine. For **Phase 4** (collaborative filtering + Lightning AI training setup) and **Phase 8** (cinematography CV pipeline), use a higher thinking effort level — these are the two most correctness-critical, multi-step phases in the project, and it's worth the extra tokens/latency to get the pipeline design and training setup right the first time rather than debugging a rushed version later.

---

## END-OF-PHASE PROGRESS REPORT FORMAT

Every phase ends with a report in this shape before asking permission to continue:

1. **What was built** — concise summary of the modules/endpoints/models/UI added this phase.
2. **How to verify it** — concrete steps I can take to test it myself (a URL to hit, a command to run, a page to view).
3. **Assumptions made** — anything you decided on my behalf (e.g. a vote-count threshold, a default weighting) and the reasoning, so I can override it if needed.
4. **What's needed from me before the next phase** — credentials (e.g. Lightning AI User ID + API Key), design direction, files to supply, decisions to make, or "nothing, ready when you are."
5. **Explicit go-ahead question** — e.g. "Ready to move to Phase X, or would you like changes first?"

---

## PHASE BREAKDOWN

### Phase 1 — Project Setup & Architecture
Initialize the Django project with separate apps per domain (`users`, `movies`, `ratings`, `recommendations`, `cinematography`, `admin_panel`). Set up MySQL connection, environment config (`.env`, never hardcode secrets), Django REST Framework, session auth settings, and CORS config for the future React app. Set up the Git structure and a clean modular folder layout. No business logic yet — just scaffolding. **Ask permission before Phase 2.**

### Phase 2 — Core Data Models & TMDB Integration
Define models: `Movie` (include a `source_tags` or similar field to later mark whether a film came from TMDB's general catalog, a scraped technique list, or both), `Genre`, `Person` (cast/director), `Rating`, `WatchlistItem`, and user profile extensions. Build a standalone TMDB service module (not tangled into views) that fetches movie details, poster paths, and trailer keys.

Write a management command to populate the DB with the **top 10,000 highest-rated movies from TMDB** (via the discover/top-rated endpoint, sorted by vote average). Apply a minimum vote-count threshold before ranking by rating (ask me what threshold I want, or propose one with clear reasoning — e.g. 200+ votes — rather than silently picking a number) so the list reflects genuinely well-regarded films rather than obscure titles with a handful of perfect votes. Note that TMDB's paginated endpoints cap at 500 pages × 20 results, so 10,000 is the practical ceiling without switching data sources — flag it if this limit is a problem.

Confirm poster/trailer embedding works in a raw API response before moving on. **Ask permission before Phase 3.**

### Phase 3 — Content-Based Filtering Engine
Build the content-based similarity module (TF-IDF or embeddings, as a swappable, testable service class) using genre/overview/cast/director/keywords. Compute and cache the similarity structure. Expose it only as an internal service for now (no API endpoint yet). **Ask permission before Phase 4.**

### Phase 4 — Collaborative Filtering Engine & Lightning AI Training
Prepare the collaborative filtering training pipeline (SVD/KNN on MovieLens) as a Lightning AI training job. When you need my Lightning AI credentials (`LIGHTNING_USER_ID` + `LIGHTNING_API_KEY`), ask me for them explicitly. Use them to run training on Lightning AI yourself. Export the trained model artifact and build the loading/integration logic on the backend. Follow the training fallback protocol in Global Rule 7 if credits run out. **Ask permission before Phase 5.**

### Phase 5 — Hybrid Engine & Core API Endpoints
Merge content-based, collaborative, and popularity scores into a single hybrid scoring service (weights should be configurable, not hardcoded). Expose the full core API surface: auth endpoints, movie search/detail, rate/watchlist, and recommendations. Add Swagger/API docs so the backend is fully testable without a frontend. This completes the **core backend**. **Ask permission before Phase 6.**

### Phase 6 — Core Frontend Integration
**Stop and ask me for my design ideas before writing any UI.** Once I've given direction, build the React app: session-based auth flow (with CSRF handling), search, movie detail pages with embedded poster/trailer, rating, watchlist, and the recommendation feed — all wired to the Phase 5 API. This completes the full **core system**, end to end. **Ask permission before Phase 7.**

### Phase 7 — Scraping-Fed Technique Dataset Pipeline
I will scrape the source lists myself; you tell me precisely what to extract and where to save it. Two confirmed sources:

- **Letterboxd — "Top 1,000 Films of All Time (Calculated)"** (`https://letterboxd.com/prof_ratigan/list/top-1000-films-of-all-time-calculated/`): paginated, 100 films per page across 10 pages (`.../page/2/`, `.../page/3/`, … `.../page/10/`). The grid view exposes title + rank per film but not year — year will need to be resolved via TMDB title matching during ingestion, not guessed.
- **They Shoot Pictures, Don't They? — "1,000 Greatest Films"** (`https://theyshootpictures.com/gf1000_rank1-1000.htm`): this specific page renders its film data client-side (the raw HTML only contains template placeholders, not actual film data), so a standard scraper will likely return nothing useful from it directly. Before assuming this source can be scraped, check whether the site's "plain" list view or "sortable table" view (linked from the same page) renders the data statically instead. If neither works cleanly, stop and tell me — do not guess at a workaround or invent data to fill the gap.

For each confirmed source, tell me: (a) exact fields to extract (title, rank/position, year if available, director if available), (b) the exact file format and folder path to save output to (one file per source, e.g. `/data/raw/technique_sources/letterboxd_top1000.json`, `/data/raw/technique_sources/tspdt_top1000.json`).

Build the ingestion pipeline: normalize titles, **fuzzy-dedupe across both scraped sources first** (a film appearing on both lists must only be stored once — merge its source citations rather than creating duplicate entries), then **merge the deduped result into the main `Movie` catalog from Phase 2** — matching against the existing ~10,000 TMDB entries by TMDB ID (resolved via title+year lookup) so a film already in the catalog isn't duplicated, and only genuinely new titles are added as new `Movie` rows.

**The "film-student" / technique-source flag applies strictly and only to films that were actually scraped from these two sources.** A film should never receive this flag just because it's popular, critically acclaimed, or thematically similar to other technique-tagged films — the flag is a direct record of "this title appeared on the Letterboxd list and/or the TSPDT list," nothing more. Do not infer or extend this flag onto other catalog movies. The final flagged set will be at most ~2,000 films — do not force it to hit any particular number, and do not add films to it beyond what the two scrapes actually produced.

This does not touch the core system's recommendation logic or endpoints, only the shared `Movie` table. If at any point you can't scrape or ingest a source as expected, ask me for that part rather than working around it with placeholder or fabricated data. **Ask permission before Phase 8.**

### Phase 8 — Cinematography CV Pipeline (Curated Subset)
Select the curated cinematography-analysis subset (**exactly 500, or fewer if the scraped technique-source set is smaller than 500 — never pad it with non-technique-source films to reach 500**) from films carrying the technique-source flag from Phase 7. If the flagged set is large enough, prioritize films cited by both scraped sources first, then fill the remainder from single-source citations.

Build the analysis pipeline: shot detection (PySceneDetect) for average shot length/pacing, OpenCV color analysis, optical-flow-based motion energy. I am supplying the trailer files myself — do not attempt to auto-download them. Tell me exactly which films you need trailers for, what file format/naming convention to use, and what folder path to place them in (e.g. `/data/raw/trailers/<tmdb_id>.mp4`), then wait for me to supply them before running analysis on those files.

Tell me if any analysis step should run as a Lightning AI job for compute reasons (following the same credentials and training-fallback protocol as Phase 4), and use the credentials to run it if so. Store the resulting vectors in a dedicated model, kept fully separate from the core recommendation models. **Ask permission before Phase 9.**

### Phase 9 — Technique Features, Visualizations & Their Frontend
Build the backend pieces: technique taxonomy/explorer endpoints, the "same technique, different films" comparator, style-similarity scoring, crowdsourced tag submission with an admin-approval queue (covering the full catalog, not just the 500), and the weekly spotlight logic. **Stop and ask me for design ideas before building this section's frontend** (charts — bar/scatter/pie — comparator UI, quiz mode, tagging UI). **Ask permission before Phase 10.**

### Phase 10 — Optimization, Testing & Final Polish
Full pass for query optimization, indexing, and caching across both the core and cinematography systems. Add unit tests for model/API logic. Do a full debugging pass across all modules. Finalize documentation (setup instructions, API docs, architecture overview). Confirm everything still works end-to-end before considering the project complete.

---

## BEFORE YOU START

Confirm you understand these constraints, then begin Phase 1. Do not skip ahead. Do not combine phases. Always pause for my explicit go-ahead using the progress report format above.
