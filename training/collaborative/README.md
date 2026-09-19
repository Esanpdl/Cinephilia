# Phase 4 collaborative training

All source is kept in this project. `build_model.py` orchestrates evaluation and
the final fit; `sgd.py` contains the complete biased matrix-factorization training
algorithm. No training is hidden in a remote notebook.

## Data

The exact input is `data/collaborative/prepared/`: authentic MovieLens 32M ratings
linked to the existing TMDB catalog by ID, checked against catalog IMDb IDs when
both sources supply them. Missing, conflicting and out-of-catalog links are
recorded in `excluded_links.json`, never guessed. No Django users or their ratings
are included. MovieLens user IDs are anonymized source identifiers, not site accounts.

The prepared manifest records the official archive SHA-256 and each prepared
file's checksum. The local raw archive is obtained from
[GroupLens](https://grouplens.org/datasets/movielens/32m/). Its four CSV checksums
are checked against the [official README](https://files.grouplens.org/datasets/movielens/ml-32m-README.html).
The actual README/license and checksums travel with the prepared dataset. This
college research project must preserve the dataset's terms and attribution.

To regenerate the prepared data from the complete Cinephilia project:

```powershell
.\.venv\Scripts\python.exe backend/manage.py export_collaborative_catalog
.\.venv\Scripts\python.exe scripts/download_movielens.py
.\.venv\Scripts\python.exe scripts/prepare_collaborative_data.py
```

## Training and evaluation

The prediction is a global mean, a user bias, a movie bias and the dot product
of 32 learned user/movie factors. SGD optimizes only observed ratings. Missing
ratings are never treated as zero ratings. The fixed seed, learning rate,
regularization and epoch settings are in `config.json`.

1. Partition ratings globally by timestamp into approximately 80% training,
   10% validation and 10% test, keeping timestamp ties in the same partition.
2. Fit only movies with at least 20 training-period ratings. Compare validation
   predictions with a separately fitted regularized bias baseline. Select the
   best epoch on a fixed authentic validation sample; never select on the test set.
3. Measure RMSE and MAE on the untouched test period. Also evaluate the deployment
   inference path on up to 2,000 eligible real user histories: estimate a new
   user vector from fixed item factors and training-period ratings only.
4. After recording evaluation, refit the selected number of epochs on all eligible
   MovieLens ratings. This improves current item coverage. Reported holdout metrics
   belong to the pre-refit model; they are not test scores for the final refit.
5. Export fixed movie factors, biases, support counts, metadata and evaluation as
   NPZ/JSON. The backend estimates a site's user's taste vector from their own
   ratings; it never indexes a Django user ID into a MovieLens user-factor array.

These are catalog-conditioned offline rating-prediction metrics, not a claim
about click-through or top-N ranking quality. The current TMDB catalog is newer
than MovieLens's last ratings. Uncovered movies and profiles with fewer than
three covered ratings produce no CF prediction; Phase 5 handles hybrid fallbacks.
MovieLens ratings 0.5–5 convert to the site's 1–10 scale by multiplying by two.

## Run the exact bundle

Normally the assistant runs it on Lightning. If you choose the manual fallback,
extract the ZIP and use Python 3.11 or 3.12 from its root:

```powershell
python -m venv .cf-venv
.\.cf-venv\Scripts\python.exe -m pip install -r training/collaborative/requirements.txt
.\.cf-venv\Scripts\python.exe training/collaborative/build_model.py --prepared data/collaborative/prepared --output data/collaborative/artifacts/phase4
```

On Linux use `.cf-venv/bin/python`. The Lightning runner uses the dedicated
Studio's provided environment and does not create a second environment.
Choose a new output folder each time. Return its entire contents:
`model.npz`, `movies.json`, `evaluation.json`, and `manifest.json`.

Copy the folder into Cinephilia, then activate and inspect it:

```powershell
.\.venv\Scripts\python.exe backend/manage.py activate_collaborative_model data/collaborative/artifacts/phase4
.\.venv\Scripts\python.exe backend/manage.py collaborative_movies --demo --limit 10
```

The demo is an authentic, attributed MovieLens history saved with the evaluation
evidence. It is not a fabricated site user or an independent quality benchmark.

## References

- Harper and Konstan (2015), [The MovieLens Datasets: History and Context](https://doi.org/10.1145/2827872).
- [Biased SVD equations and observed-rating SGD](https://surprise.readthedocs.io/en/stable/matrix_factorization.html) (algorithm reference; the project's explicit implementation is in `sgd.py`).
- [Numba's supported dependency versions](https://numba.readthedocs.io/en/0.61.2/user/installing.html#version-support-information).
