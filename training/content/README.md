# Content index training bundle

The project runs this build on Lightning AI. Use the manual steps below only if
you choose the fallback after a Lightning failure. No database, TMDB or Lightning
credentials are needed to run the extracted bundle.

## Dataset and configuration

`data/content/catalog.json` is the exact export of the project's real TMDB
catalog: 9,999 movies, with titles, overviews, genre IDs, keyword IDs, cast and
directors. The builder verifies the embedded catalog SHA-256 before fitting.
No user accounts, ratings, passwords or API keys are included.

`training/content/config.json` controls the five feature weights and cache size.
Defaults: overview 35%, keywords 25%, genres 20%, cast 10%, directors 10%.
Cast uses the first ten distinct billed people; all directors are included.
Missing metadata stays missing. TMDB cannot guarantee every field or trailer.

## Run after extracting the ZIP

Use Python 3.11 or 3.12. From the extracted bundle's root:

```powershell
python -m venv .content-venv
.\.content-venv\Scripts\python.exe -m pip install -r training/content/requirements.txt
.\.content-venv\Scripts\python.exe training/content/build_index.py --snapshot data/content/catalog.json --output data/content/artifacts/phase3
```

On Linux/macOS use `.content-venv/bin/python` instead. An ordinary CPU is enough;
the sparse index is built in batches and no GPU is required. Choose a fresh
output directory for each build; existing artifacts are never overwritten.

## Return and activate

Return the entire `data/content/artifacts/phase3` folder (ZIP is fine). It must
contain `manifest.json`, `features.npz`, `neighbors.npz`, `movies.json`, and
`feature_schema.json`. Copy that folder to the same location in Cinephilia, then:

```powershell
.\.venv\Scripts\python.exe backend/manage.py activate_content_index data/content/artifacts/phase3
.\.venv\Scripts\python.exe backend/manage.py similar_movies 238 --limit 10 --explain
```

Activation verifies checksums, shapes, IDs and normalization before replacing
`data/content/current.json`. The internal loader notices pointer changes. Keep
active artifact files immutable; build a new folder when metadata changes.
Inference needs the backend requirements only, with no scikit-learn or pickle.
