"""Build a TF-IDF catalog index on Lightning (or an explicitly approved fallback)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
import scipy
from scipy import sparse
import sklearn

from apps.recommendations.services.content.artifacts import (
    DATA_FILES, ENGINE_VERSION, FORMAT_VERSION, canonical_json, sha256_file, write_json,
)
from apps.recommendations.services.content.features import fit_features
from apps.recommendations.services.content.ranking import build_neighbors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "training/content/config.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output directory already exists; choose a new artifact directory.")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != 1:
        raise SystemExit("Unsupported snapshot version.")
    movies = snapshot["movies"]
    catalog_hash = hashlib.sha256(canonical_json(movies).encode("utf-8")).hexdigest()
    if catalog_hash != snapshot["catalog_sha256"]:
        raise SystemExit("Catalog snapshot checksum does not match its contents.")
    ids = np.array([movie["tmdb_id"] for movie in movies], dtype=np.int64)
    if len(ids) == 0 or len(np.unique(ids)) != len(ids) or np.any(ids <= 0) or np.any(np.diff(ids) <= 0):
        raise SystemExit("Snapshot IDs must be unique positive TMDB IDs in ascending order.")
    started = time.perf_counter()
    print(f"Fitting five TF-IDF fields for {len(movies)} authentic catalog movies.", flush=True)
    matrix, schema = fit_features(movies, config)
    fit_seconds = time.perf_counter() - started
    print(f"Features ready: {matrix.shape}, {matrix.nnz} nonzero entries.", flush=True)
    neighbors, scores = build_neighbors(matrix, ids, config["neighbors_per_movie"], config["similarity_batch_size"], progress=lambda message: print(message, flush=True))
    args.output.mkdir(parents=True)
    sparse.save_npz(args.output / "features.npz", matrix, compressed=True)
    np.savez_compressed(args.output / "neighbors.npz", indices=neighbors, scores=scores)
    write_json(args.output / "movies.json", movies)
    write_json(args.output / "feature_schema.json", schema)
    manifest = {
        "format_version": FORMAT_VERSION, "engine": ENGINE_VERSION,
        "catalog_sha256": catalog_hash, "snapshot_exported_at": snapshot["exported_at"],
        "created_at": datetime.now(timezone.utc).isoformat(), "config": config,
        "movie_count": len(movies), "feature_count": matrix.shape[1], "nonzero_features": matrix.nnz,
        "zero_feature_movies": ids[np.asarray(matrix.getnnz(axis=1)).ravel() == 0].tolist(),
        "neighbor_count": neighbors.shape[1],
        "fit_seconds": fit_seconds, "build_seconds": time.perf_counter() - started,
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
        "files": {name: sha256_file(args.output / name) for name in DATA_FILES},
    }
    write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
