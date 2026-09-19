# Cinephilia

A phased college capstone: hybrid movie recommendations followed by a separate
film-student cinematography learning layer. Current scope: **expanded catalog and models,
curated homepage, optional public reviews, official Letterboxd embed, and the
500-film student collection with color studies of sampled footage**. See the
[film-student guide](docs/film-student-guide.md), [expansion report](docs/catalog-expansion.md)
and [local trailer downloader instructions](data/raw/technique_sources/webScraping/TRAILERS.md).

The runnable palette extractor and review inputs are preserved under
[`training/visual/`](training/visual/README.md). The current
[replacement video list](docs/source-replacements.md) gives film names and filenames.

## Open the website

The configured workspace uses the existing Supabase database and trained artifacts.
Install frontend dependencies once, then start both local services:

```powershell
Set-Location frontend
npm.cmd ci
Set-Location ..
& ./scripts/start_dev.ps1
```

Open **http://127.0.0.1:5173/**. The helper starts missing services in hidden windows;
logs and process IDs are in `data/phase6/`. See the [frontend guide](frontend/README.md)
and [Phase 6 report](docs/phase-6.md) for routes, verification, and development details.

## Setup (PowerShell, Python 3.11 or 3.12)

Run from the `Cinephilia` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env # only if .env does not exist
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

Set `DJANGO_SECRET_KEY` to the generated value. The initial workspace already has
a generated key in its ignored `backend/.env`; preserve it.
Set `DATABASE_URL` to your actual Supabase PostgreSQL URI from **Dashboard → Connect →
Session pooler**, port **5432**. Replace the password placeholder and percent-encode
reserved password characters. A direct connection is also supported if reachable.
No SQLite/MySQL fallback is used. Django owns authentication and database sessions;
Supabase supplies PostgreSQL, so anon/service-role keys are not needed.

```powershell
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py check_database
.\.venv\Scripts\python.exe backend/manage.py prepare_database
.\.venv\Scripts\python.exe backend/manage.py migrate --plan
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py runserver
```

`check_database` performs a read-only PostgreSQL/TLS check. Migrations create Django's
built-in auth/session/admin tables and the Phase 2 catalog, rating and profile tables.
Use a dedicated development Supabase project. `prepare_database` creates the
`cinephilia` schema; Django's search path places its tables there, outside Supabase's
default public Data API schema. Keep `cinephilia` out of Data API exposed schemas.
Browser clients will access Django REST only.

`http://127.0.0.1:8000/admin/` is Django's built-in administration interface.
Optionally run `backend/manage.py createsuperuser` with the venv Python to use it.
The read-only movie detail API is at `/api/v1/movies/<tmdb_id>/` after import.
For example, open `http://127.0.0.1:8000/api/v1/movies/238/` for The Godfather.
The root URL and other reserved routes return 404 until their feature phases.

## Boundaries

See [architecture](docs/architecture.md), [Phase 1 report](docs/phase-1.md), and
[Phase 2 import and verification](docs/phase-2.md), and
[Phase 3 content similarity](docs/phase-3.md), and
[Phase 4 collaborative filtering](docs/phase-4.md), and
[Phase 5 core API and Swagger guide](docs/phase-5.md), and
[Phase 6 core frontend](docs/phase-6.md), and
[Phase 7 source data and people search](docs/phase-7.md).
For optional advance data collection by another AI, use the
[scraping handoff prompt](docs/scraping-handoff-prompt.md). Its outputs are reserved
for the technique-data ingestion pipeline.
All product UI lives in the React application. Django serves its built-in
admin and developer API documentation. REST uses session auth with CSRF protection.
Open `http://127.0.0.1:8000/api/docs/` to register/login and exercise the core APIs.
Use the same hostname for React and Django in development (`localhost` on both,
or `127.0.0.1` on both), and send `credentials: 'include'` on API requests.
Writes require the CSRF token, including anonymous login/registration. Frontend origins default to port 5173 in
the environment example; CORS and CSRF origins are explicit allowlists.

Production defaults use secure cookies and HTTPS. Set `DJANGO_DEBUG=False`, a unique
secret, real allowed hosts and HTTPS origins before deployment; serve collected
static files and configure the trusted proxy for the selected hosting platform.
Deployment is outside Phase 1.

## Lightning AI

Training dependencies are isolated in `training/requirements.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r training/requirements.txt
# Populate training/.env using training/.env.example.
.\.venv\Scripts\python.exe scripts/check_lightning.py
```

The check loads both `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` from the ignored
training environment file and verifies them with the SDK's read-only account API.
The project uses SDK 2026.9.15 from native Windows. The earlier 0.2.23 SDK used
a retired upload endpoint; the current version supports Lightning's blob API.
Environment authentication is officially supported and avoids browser login when
both values are supplied. No training job or paid compute is started in Phase 1.

Phase 3 uses a CPU Studio to fit the content index; see its report for build,
activation and verification commands. `training/content/requirements.txt` holds
the scientific dependencies separately from the Lightning orchestration SDK.
The [training code and evidence guide](training/README.md) maps each training
step to its source file and the local records retained for teacher review.

## Frontend direction

- Motion components: [Be UI](https://beui.dev/components/motion).
- Aesthetic reference: [Criterion Channel film catalog](https://films.criterionchannel.com/).
- Approved layout: featured-film hero, editorial rows, separate browse grid, dedicated film pages.
- Cinematic framing, shadow, typography, grain, and restrained motion supply the auteur feeling.
- Director references affect presentation only; film ranking and recommendations have no added director preference.
- Future learning-section design remains subject to the brief's separate design checkpoint.

## Sources

- [Supabase connection modes and SSL](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Lightning CLI authentication](https://lightning.ai/docs/overview/ai-studio/cli)

Secrets, raw datasets, trailers, and model artifacts are ignored by Git. The original
prompt and `main.py` are preserved. No film facts or sample datasets have been invented.
