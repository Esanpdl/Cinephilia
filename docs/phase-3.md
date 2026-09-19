# Phase 3: internal content similarity

## Scope

**Complete and active.** The content model was fitted on Lightning AI's CPU-4,
downloaded, verified against the authentic snapshot and activated locally.
Phase 4 has not started.

`backend/apps/recommendations/services/content` owns the engine:

- `contracts.py`: replaceable `ContentSimilarity` interface and typed results/errors.
- `snapshot.py`: three bulk catalog reads in a consistent read-only transaction.
- `features.py`: fitting logic, used only by the training script.
- `ranking.py`: exact batched cosine ranking with deterministic TMDB-ID tie breaks.
- `engine.py`: immutable sparse inference, cached neighbors and explanations.
- `artifacts.py` / `registry.py`: checksums, validation, atomic activation and process cache.

There is no recommendation endpoint yet. Future hybrid code imports
`get_content_service()` and calls `similar()` or `score_candidates()`.
Diagnostic metadata and explanations are specific to the TF-IDF implementation.

## Features and assumptions

| Field | Weight | Representation |
| --- | ---: | --- |
| Overview | 35% | English stopwords removed; unigrams/bigrams; at most 40,000 terms |
| Keywords | 25% | Whole TMDB keyword IDs |
| Genres | 20% | Whole TMDB genre IDs |
| Cast | 10% | First ten distinct billed people, identified by TMDB person ID |
| Directors | 10% | All distinct directors, identified by TMDB person ID |

Each block is TF-IDF/L2 normalized, multiplied by the square root of its weight,
and concatenated. The final vector is normalized again. This makes cosine
contributions proportional to the intended weights when every field is present;
missing fields change the effective proportions through final normalization.
People's names are not split into words. All weights and limits live in
`training/content/config.json`; changing them requires a new build.

These are transparent starting weights, not learned or quality-optimized weights.
Text is the catalog's TMDB `en-US` metadata; some records can lack translated
overviews. Empty fields remain empty, and a movie with no features gets no
positive matches. No plot, credit, keyword or trailer data is invented.

This uses scikit-learn's [TF-IDF vectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html).
Dot products of normalized vectors yield [cosine similarity](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html).

## Cache and artifact behavior

- Sparse float32 features; only 128 x catalog-size scores are temporarily dense.
- Top 100 positive matches per film; the query film is always excluded.
- More matches or exclusions beyond the cache use an exact sparse row product,
  with a bounded 256-query in-memory cache. Ties sort by ascending TMDB ID.
- `similar()` accepts limits 1–1,000. Unknown query IDs raise `MovieNotIndexed`.
- `score_candidates()` returns zero for unknown candidates; raw self-similarity
  can be one. Future callers must exclude watched/query films when appropriate.
- Explanations report actual shared metadata and each field's score contribution.
- Files are JSON/NPZ, with SHA-256 checksums and no pickle. Loading verifies
  dimensions, IDs, normalization and cached indices before activation.
- An index represents a frozen catalog snapshot. New/changed metadata requires
  rebuilding; it is never fitted during a request. Active artifact directories
  must remain immutable. Keep prior folders to roll back by reactivating them.

## Rebuild on Lightning

From the `Cinephilia` project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r training/requirements.txt
.\.venv\Scripts\python.exe backend/manage.py export_content_snapshot
.\.venv\Scripts\python.exe scripts/package_content_training.py
.\.venv\Scripts\python.exe scripts/train_content_lightning.py
```

The runner loads the existing `training/.env` credentials, creates a dedicated
CPU Studio with teamspace secret injection disabled, uploads an explicit allowlist
ZIP, builds, stops the Studio so its files synchronize, then downloads and verifies the artifact. It
records sanitized stage/error/cleanup details under `data/content/runs`.
The build uses the dedicated Studio's provided Python environment because this
account does not permit an additional virtual environment. Each current runner
attempt archives its exact source ZIP, orchestration script and remote build log
for reproducibility and teacher review; see [the evidence guide](../training/README.md).
Python 3.11/3.12 and NumPy 1.26.4 are pinned for compatibility with the Studio's
bundled pandas. A NumPy 2.x attempt failed at pandas import before any fitting;
the failed receipt and log are retained. The backend uses the same NumPy pin.
It never automatically runs training locally after a remote failure.

`data/content/cinephilia-content-training.zip` includes the exact 9,999-movie
snapshot, scripts, pinned dependencies and [manual fallback instructions](../training/content/README.md).
It excludes credentials, user accounts and ratings. Use that fallback only after
the user chooses it, per the master brief's training rule.

## Activate and inspect

The active, verified artifact is `data/content/artifacts/20260916-025513-6bcdf4`:

```powershell
.\.venv\Scripts\python.exe backend/manage.py activate_content_index data/content/artifacts/20260916-025513-6bcdf4
.\.venv\Scripts\python.exe backend/manage.py similar_movies 238 --limit 10 --explain
.\.venv\Scripts\python.exe scripts/verify_phase3.py --artifact data/content/artifacts/20260916-025513-6bcdf4
```

`verify_phase3.py` runs numerical contract tests without fitting a model. With a
real artifact, it also checks metadata against the authentic snapshot and compares
sampled cached/fallback rankings to an independent full sort, including exclusions,
candidate scores, explanations and zero database queries during inference.

## Verified results (2026-09-16)

| Measurement | Observed result |
| --- | --- |
| Authentic movies indexed | 9,999 |
| Feature columns / nonzero entries | 99,595 / 513,607 |
| Movies with no features | 0 |
| Cached neighbors per movie | 100 |
| Remote fit / complete index build | 1.27 s / 4.98 s (setup and transfers additional) |
| Artifact size | 36,479,896 bytes, approximately 34.79 MiB |
| Local cold load | 0.87 s |
| Mean cached lookup, 100 calls | 0.26 ms |
| Inference database queries | 0 |

Seven numerical/activation contract tests pass. Real-artifact verification compares
31 sampled rows (including The Godfather) against an independent full sort at
limits 10, 100 and 110, checks exclusions beyond the neighbor cache, candidate
scores, explanation sums and field-weight normalization. The full stored movie
metadata exactly matches the snapshot. Django and dependency checks pass.
Timings are measurements on this run/environment, not production guarantees.

The Godfather's first three matches are The Godfather Part II (0.531382),
The Godfather Part III (0.385127) and The Cotton Club (0.309396). Explanations
show the actual shared TMDB metadata. This is a sanity check, not a held-out
recommendation-quality benchmark; quality tuning can be evaluated separately.

Training completed in run `20260916-025001-a2404d`. Its immediate download returned
404; after the Studio stopped, recovery run `20260916-025513-6bcdf4` successfully
downloaded the same completed artifact without fitting again. The final Studio
status is **Stopped**. Both receipts, the original training log, exact uploaded
source bundles and orchestration scripts remain under `data/content/runs`.
The current runner stops before downloading and offers `--recover-run <run-id>`
for a completed build whose download failed.

## Next-phase handoff

Phase 4 requires explicit approval under the master brief. Existing Lightning
credentials are configured. The user reports both Letterboxd and TSPDT source
lists have been scraped; reserve their TMDB matching/enrichment for Phase 7.
Their contents and paths have not been verified in Phase 3.
