# Phase 1 progress

**Status: complete. Awaiting explicit approval for Phase 2.**

## Built

- Django 5.2 project with six domain app scaffolds and separate URL/service packages.
- DRF session authentication, authenticated-by-default permissions, CSRF middleware,
  and explicit credentialed CORS allowlists for a future React application.
- Supabase PostgreSQL configuration with required TLS, connection health checks,
  timeout and environment-driven credentials. No alternate database fallback.
- Dedicated `cinephilia` PostgreSQL schema and an idempotent `prepare_database`
  command; initial Django tables are outside the default public Data API schema.
- Environment templates, ignored local secrets, dependency locks, WSGI/ASGI entry
  points, architecture/setup documentation and a read-only database check command.
- Lightning SDK authentication check; credentials verified against the account API.
- Future frontend directories and the user's two UI references recorded.

## Verified

- Installed backend and training dependencies; `pip check` passes.
- Django system check passes with the configured Supabase database.
- Live PostgreSQL connection verified with TLS active through the session pooler.
- All 18 built-in Django migrations applied; `migrate --check` passes.
- Live schema check confirms auth/session/migration tables live in `cinephilia`.
- Database session save/load succeeds inside a transaction rolled back afterward.
- Built-in admin login renders successfully and provides the CSRF cookie.
- All project Python sources compile.
- Offline middleware probes verify credentialed CORS for the configured origin,
  rejection of a foreign origin, default anonymous-access denial and authenticated
  session writes requiring CSRF.
- Git ignores both local environment files and the virtual environment.
- Lightning read-only account request succeeds; no compute resources created.

## How to verify

From the `Cinephilia` folder:

```powershell
.\.venv\Scripts\python.exe backend/manage.py check --database default
.\.venv\Scripts\python.exe backend/manage.py check_database
.\.venv\Scripts\python.exe backend/manage.py migrate --check
.\.venv\Scripts\python.exe backend/manage.py showmigrations
.\.venv\Scripts\python.exe backend/manage.py runserver
```

Open `http://127.0.0.1:8000/admin/login/`. Product endpoints and React UI arrive in
their approved later phases. No superuser was created during setup.

The user's session pooler URI is configured in ignored `backend/.env`, with the
password percent-encoded. Supabase HTTP API keys are not used for this connection.

## Assumptions

- Supabase hosts PostgreSQL; Django retains session authentication.
- Python 3.11 and Django 5.2 are used with pinned installed dependencies.
- Supabase session pooling on 5432 supports the local IPv4 environment.
- Django's built-in User will receive profile extensions in Phase 2.
- Local React development will use port 5173; timezone is Asia/Kathmandu.

## Limitations and next phase

`lightning login` cannot start in the installed CLI on native Windows because
`simple-term-menu` imports Unix-only `termios`. The SDK authentication path is
working and documented instead.

The Criterion reference timed out during retrieval; revisit in the frontend phase.
No UI is implemented yet. Phase 2 has not started. The master prompt's Phase 1
instruction says "Ask permission before Phase 2." Phase 2 will need a TMDB API
credential and an agreed minimum vote-count threshold for catalog import. Propose
200 votes to exclude titles with very few ratings, subject to user confirmation.
