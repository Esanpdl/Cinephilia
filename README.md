# Cinephilia

A film discovery and cinematography study application built with React,
TypeScript, Django REST Framework and PostgreSQL. It includes hybrid film
recommendations, accounts and reviews, watchlists, public cinema profiles,
still-image studies, colour palettes, frame comparisons and technique moderation.

## Requirements

- Python 3.11 and Node.js 22.12 or newer
- PostgreSQL with TLS (including a Supabase direct/session connection)
- Your own database, Django secret and optional TMDB/email credentials

See [SETUP.txt](SETUP.txt) for installation and private runtime-bundle commands.
Copy the supplied `.env.example` files to local `.env` files and fill them in.
Never commit credentials. Frontend variables are visible to browser users.

## Source and runtime data

This repository contains application source, migrations, pinned dependencies,
startup scripts and scraping utilities. It deliberately excludes the database,
film frames, colour signatures and trained models. A source-only checkout can
start against a configured database but does not reproduce the populated site.

The complete experience needs a separately supplied private runtime bundle.
That bundle contains reference catalogue and study records, active recommendation
models, frames and colour signatures. It excludes accounts, personal interactions,
passwords and sessions. Create your own administrator after importing reference
data. Runtime inference does not need a GPU.

The supplied bundle is versioned by checksums. Its database source is a dated
snapshot, not an assurance that a remote database is currently available.

## Layout

- `backend/`: API, database models, migrations and management commands
- `frontend/`: React application, styles and required static artwork
- `scripts/`: local startup and private runtime-bundle tools
- `data/raw/technique_sources/`: scraping source and dependency templates

## Data and credits

Film metadata and artwork are provided by TMDB; trailers are YouTube embeds.
Collaborative recommendations use a model fitted to catalogue-linked MovieLens
ratings. Content recommendations use weighted TF-IDF features. Film studies use
measured colour distributions and separately identified human-reviewed and
model-suggested technique evidence. Match scores are similarity scores, not
probabilities of enjoyment. Image and dataset rights remain with their owners;
this source repository does not grant permission to redistribute those datasets.
See `frontend/THIRD_PARTY_NOTICES.md` for interface credits.

Development settings are not a production deployment configuration. Configure
HTTPS, secure cookies, explicit hosts/origins and a production application server
before exposing the application publicly.