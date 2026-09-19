# Training code and evidence for project review

All training source code is kept inside this project. It is not confined to a
Lightning notebook or temporary remote session.

The film-student trailer extractor is separate from these trained recommendation
models. It uses deterministic OpenCV measurements and a pretrained text detector;
no new CV training job was run. See the [film-student guide](../docs/film-student-guide.md)
and `visual-requirements.txt` for its method, limitations and local evidence.

The full runnable palette extraction source is also preserved in
[`training/visual/`](visual/README.md), including the algorithm, batch runner,
dependency pins and source checksums. Verify it against the application code
with `scripts/preserve_visual_extraction.py --check`.

## Phase 3: content-based model

| What to show | Project file |
| --- | --- |
| Training entry point | `training/content/build_index.py` |
| TF-IDF fitting and weighted feature construction | `backend/apps/recommendations/services/content/features.py` |
| Cast/director/keyword/genre identity handling | `backend/apps/recommendations/services/content/metadata.py` |
| Batched cosine calculation and neighbor caching | `backend/apps/recommendations/services/content/ranking.py` |
| Feature weights and build settings | `training/content/config.json` |
| Exact scientific dependency versions | `training/content/requirements.txt` |
| Lightning job orchestration | `scripts/train_content_lightning.py` |
| Consistent export of authentic TMDB metadata | `backend/apps/recommendations/services/content/snapshot.py` |
| Credential-free source/dataset bundle creation | `scripts/package_content_training.py` |
| Model loading and inference | `backend/apps/recommendations/services/content/engine.py` |
| Correctness verification | `scripts/verify_phase3.py` |

### Explain the training process

1. Export the imported TMDB catalog, including genres, overview, cast, directors
   and keywords. This snapshot contains no user accounts or ratings.
2. Fit a separate TF-IDF vocabulary and inverse-document-frequency weights for
   each field. The model learns how common each term/entity is across the catalog.
3. Normalize each field, apply configurable weights, concatenate the fields and
   normalize the complete movie vector.
4. Compute cosine similarities in batches and save each movie's top 100 matches.
5. Download the sparse vectors and neighbor cache from Lightning. Verify their
   checksums and activate the artifact for internal inference.

This is an unsupervised content model. There are no target labels, neural-network
epochs or supervised accuracy scores in this phase. The five field weights are
chosen configuration values; the TF-IDF statistics are fitted to the real catalog.
Explain correctness tests separately from recommendation-quality evaluation.

### Local evidence retained

- `data/content/catalog.json`: exact authentic training snapshot and its checksum.
- `data/content/cinephilia-content-training.zip`: source code, configuration,
  requirements, instructions and dataset sent for the build.
- `data/content/cinephilia-content-training.manifest.json`: checksum of the bundle
  and every allowed file inside it.
- `data/content/runs/*.json`: Lightning run stages, bundle checksum, outcome,
  artifact location and final Studio status. Failed attempts remain recorded.
- Successful/current runner attempts also retain `<run-id>.training.zip`,
  `<run-id>.runner.py`, and `<run-id>.log` alongside the receipt: the exact
  uploaded bundle, orchestration code, remote commands and build output.
- `data/content/artifacts/<run-id>/manifest.json`: successful build's dataset
  checksum, feature dimensions, dependency versions, timings and artifact checksums.
- `data/content/verification.json`: results from checking a successful real artifact.

Successful-build evidence appears only after the remote job and verification
complete. Failure receipts must not be presented as successful training runs.

Source code and documentation belong in Git. Local datasets, model artifacts and
run evidence are ignored by Git to avoid uploading large files; they still remain
inside the project folder for demonstration. Keep a separate backup when moving
the project between computers. Never include `backend/.env` or `training/.env`
in a teacher handoff; the credential-free training ZIP is the portable bundle.

See [run instructions](content/README.md) and the
[Phase 3 report](../docs/phase-3.md) for exact commands and current status.

## Phase 4: collaborative filtering

| What to show | Project file |
| --- | --- |
| Complete observed-rating SGD algorithm | `training/collaborative/sgd.py` |
| Chronological evaluation, model selection and final refit | `training/collaborative/build_model.py` |
| Configuration and dependency pins | `training/collaborative/config.json`, `requirements.txt` |
| Source download and published checksum verification | `scripts/download_movielens.py` |
| Exact MovieLens/TMDB identity matching and preparation | `scripts/prepare_collaborative_data.py` |
| Lightning orchestration | `scripts/train_collaborative_lightning.py` |
| Live Studio/process status and reported user/project credit balances | `scripts/check_collaborative_lightning.py --studio <studio-name>` |
| Backend profile inference and prediction | `backend/apps/recommendations/services/collaborative/math.py`, `engine.py` |
| Numerical, temporal-split and integration checks | `scripts/verify_phase4.py` |

The raw MovieLens archive, exact prepared dataset and source checksums remain
under `data/collaborative`. Source bundles, runner copies, logs and receipts live
under `data/collaborative/runs`; completed model files and evaluation evidence go
under `data/collaborative/artifacts`. These are local project files even though
large datasets/artifacts are ignored by Git.

Present the untouched test evaluation separately from the final production refit.
The final model is refitted on all eligible ratings after evaluation; those test
metrics must not be described as an independent evaluation of the refitted model.
Read [the training instructions](collaborative/README.md) and
[Phase 4 status](../docs/phase-4.md) before presenting results.
