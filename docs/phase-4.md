# Phase 4: collaborative filtering

## Status

Complete: the model was trained on Lightning CPU-4, downloaded, verified and
activated. Eight local contract tests and real-artifact integration checks pass.
The Phase 3 content index remains independently active. Phase 5 has not started.

## Actual run and results

- Successful run: `20260916-091238-097993` in Studio
  `cinephilia-collaborative-20260916-032113-ac7946`.
- Active artifact: `data/collaborative/artifacts/20260916-091238-097993`, selected
  by `data/collaborative/current.json`.
- Production model: **8,211 films (82.12% of the 9,999-film catalog)**,
  **26,539,244 ratings**, 200,948 anonymous source users and 32 factors.
  The 809 other matched films have fewer than 20 source ratings. Together with
  979 unmatched catalog films, these leave 1,788 films without CF factors.
- Validation selected epoch 14; early stopping ended evaluation training after
  epoch 17. Production refit used 14 epochs. Training/evaluation/refit took
  **255.08 seconds**, excluding setup, source loading and transfers.
- Artifacts total 1,770,457 bytes. Local loading took 35.47 ms; 20 cached-profile
  recommendation calls averaged 29.73 ms. Inference used **zero database queries**
  once history was supplied. These are local smoke-test timings, not load tests.

All errors below use the MovieLens 0.5-5 scale; lower is better.

| Evaluation | Ratings | SVD RMSE | Bias baseline RMSE | SVD MAE | Bias baseline MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Entire chronological test period | 2,654,732 | 0.94743 | 0.94965 | 0.72187 | 0.71858 |
| Backend-style inferred profiles, 2,000 eligible users | 100,490 | 0.79364 | 0.83515 | 0.58814 | 0.62063 |

The overall RMSE improvement is small and overall MAE is slightly worse than the
bias baseline. Only 8.70% of all test ratings have both a user and movie observed
during training; the warm-test SVD RMSE is 0.81499. The backend-style evaluation
shows clearer improvement but applies only to users with sufficient covered
history. It must not be generalized to cold-start users or ranking quality.

Training precedes 2018-11-09 11:01:30 UTC; validation precedes 2020-11-19
00:09:30 UTC. There are 21,231,034 eligible training ratings, 2,654,643 validation
ratings and 2,654,732 test ratings. Production refit happens after evaluation, so
the saved holdout metrics are **not an independent evaluation of the refitted
production artifact**.

Exact metrics and epoch history are in the artifact's `evaluation.json`;
`data/collaborative/verification.json` records integration checks and an actual
MovieLens user 110 demo with six source ratings. Its top results include Raiders
of the Lost Ark, The Return of the King and The Empire Strikes Back. These are
model predictions, not that user's observed scores or a universal ranking.

The successful run's `.training.zip`, `.runner.py`, `.log` and `.json` are retained
under `data/collaborative/runs`. The source bundle SHA-256 is
`d7dd9913001e0335cfd73a9ac8e5f2dd5482430b39723264ce9ca5349a2605da`.
Earlier interrupted/failed uploads remain recorded separately.

## Authentic data and identity mapping

The input is the stable [MovieLens 32M release](https://grouplens.org/datasets/movielens/32m/).
The complete archive is kept at `data/collaborative/raw/ml-32m.zip`; all four CSV
checksums match the [published GroupLens README](https://files.grouplens.org/datasets/movielens/ml-32m-README.html).
Its actual license and attribution instructions are retained with the prepared data.

The snapshot contains 9,999 catalog movies. Exact `links.csv` TMDB IDs, checked
against IMDb IDs when both sources provide one, matched 9,020 movies and
26,546,871 authentic ratings from 200,948 anonymized MovieLens users. There were
31 IMDb identity conflicts, 124 missing/invalid TMDB links and 78,410 source
movies outside this catalog. Excluded links are recorded, never guessed or
silently relabeled. Films' metadata remains the TMDB catalog's metadata.

No MovieLens users or ratings are inserted into the application database. The
public dataset is an offline training input. `Rating` continues to represent only
the site's own users; integer IDs from the two systems are never equated.

## Model and evaluation

The implementation in `training/collaborative/sgd.py` fits biased matrix
factorization (Funk SVD): global mean + user bias + movie bias + user/movie factor
dot product. It optimizes observed ratings only; unrated pairs are not zero labels.
Numba compiles the explicit update loop on a Lightning CPU. Defaults are 32
factors, at most 20 epochs, seeded initialization/shuffling, learning rate 0.007
with 0.97 decay and 0.05 regularization. These are configurable starting values,
not the result of an exhaustive hyperparameter search.

Ratings are globally split by timestamp, approximately 80/10/10, with equal
timestamps kept together. The evaluation model fits movies with at least 20
training-period ratings. A fixed validation sample selects the epoch with early
stopping. A separately fitted, regularized user/movie-bias baseline provides a
reference. The test period is used only after model selection.

An additional evaluation uses up to 2,000 eligible, authentic MovieLens histories
to exercise the same profile inference used by the backend. It estimates each
user vector from training-period ratings and fixed item factors, without reusing
the model's learned MovieLens user factors. This separates the offline training
identity from a new site's account identity.

After the held-out evaluation is recorded, the selected epoch count is fitted
again on all eligible ratings to include more recent movies. Saved test metrics
belong to the pre-refit evaluation model. They must never be presented as an
independent test of the production model after it has seen those ratings.

Metrics use MovieLens's 0.5–5 scale. They measure rating prediction on this catalog,
not click-through or top-N ranking quality. The catalog snapshot itself is newer
than the historical ratings, so this is a catalog-conditioned evaluation rather
than a recreation of a historical production catalog.

## Backend integration

- `CollaborativeFiltering` is the replaceable internal interface.
- `get_collaborative_service()` loads the class selected by
  `COLLABORATIVE_SERVICE_CLASS`, cached per process.
- `score_candidates(history, candidate_ids)` takes a map of TMDB IDs to actual
  site ratings (integers 1–10). It converts them to MovieLens scale by dividing by
  two, estimates a user bias and 32-factor vector by regularized least squares,
  then scores fixed movie factors. The saved global model is not changed.
- Predictions provide a 1–10 expected rating and a 0–1 normalized score for the
  later hybrid engine. They are estimates, not factual movie ratings.
- Fewer than three covered ratings or an uncovered candidate produces no CF
  prediction (`None`), allowing Phase 5 to choose a fallback. A CF-free profile
  does not get arbitrary personalized scores.
- `recommend()` excludes rated movies and explicit exclusions; ties sort by TMDB ID.
- `history_for_user()` reads only that Django user's ratings in one query.
  Inference after the history is supplied needs no database or network request.
- JSON/NPZ artifacts use checksums, explicit ID maps and no pickle. Activation
  validates the model before atomically replacing its independent pointer.
- The content engine, collaborative engine and future cinematography vectors
  remain separate. No recommendation HTTP endpoints were added in Phase 4.

The trained movie factors do not cover movies absent from MovieLens or below the
minimum support. New catalog entries require a future model rebuild to gain CF
coverage. Content/popularity fallback belongs to Phase 5.

## Reproduce and verify

From the Cinephilia project root:

```powershell
.\.venv\Scripts\python.exe backend/manage.py export_collaborative_catalog
.\.venv\Scripts\python.exe scripts/download_movielens.py
.\.venv\Scripts\python.exe scripts/prepare_collaborative_data.py
.\.venv\Scripts\python.exe scripts/package_collaborative_training.py
.\.venv\Scripts\python.exe scripts/train_collaborative_lightning.py
.\.venv\Scripts\python.exe scripts/verify_phase4.py
.\.venv\Scripts\python.exe scripts/verify_phase4.py --artifact data/collaborative/artifacts/20260916-091238-097993
.\.venv\Scripts\python.exe backend/manage.py collaborative_movies --demo --limit 5
```

The Lightning runner loads the existing ignored `training/.env`. It checks upload
network access before provisioning, uploads to a stopped dedicated Studio, starts
its CPU, checks the remote bundle hash, uses the provided Python environment,
trains, stops for file synchronization and downloads the artifact. Following the
user's preference, the current runner then restores CPU with the existing
auto-sleep policy; `--stop-when-done` opts out. The successful run used the earlier
stop-after-download runner, preserved alongside its receipt. Its Studio was then
restarted and confirmed Running at the user's request. Every attempt
retains its exact source bundle, runner, log and sanitized receipt. It does not
automatically fit locally on failure.

Manual fallback instructions and all needed scientific dependency pins are in
[training/collaborative/README.md](../training/collaborative/README.md). The portable
bundle contains the exact transformed ratings, source/license evidence and code.

## Film-student data handoff

The user has completed both scrapes. Phase 7 will store matched, deduplicated
movies in the shared PostgreSQL catalog, preserving source membership, ranks and
citations. Only films actually found in those lists receive the technique-source
flag. They will be available to the film-student area when its UI is implemented
in Phase 9; Phase 8's computed cinematography features cover the separately
curated subset of at most 500 source films. No scraping ingestion began here.
