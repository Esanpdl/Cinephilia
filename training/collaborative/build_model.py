"""Train/evaluate/refit a collaborative model on Lightning, preserving evidence."""
import argparse
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import platform
import sys
import time

# Small profile solves should not each launch a large BLAS thread pool.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import numba
import scipy

from apps.recommendations.services.collaborative.artifacts import DATA_FILES, ENGINE, digest, write_json
from apps.recommendations.services.collaborative.math import fold_profile, predict_items
from sgd import baseline, epoch, initialize, metrics, predict
from validation import temporal_split, validate_config


def fold_in_evaluation(users, items, ratings, train, test, state, item_counts, baseline_item_bias, config):
    _, qi, _, bi, mean = state
    train_users = users[train]
    supported_test = test[item_counts[items[test]] > 0]
    test_users = users[supported_test]
    user_counts = np.bincount(train_users, minlength=len(state[0]))
    eligible = np.unique(test_users)
    eligible = eligible[user_counts[eligible] >= config["minimum_history"]]
    rng = np.random.default_rng(config["seed"] + 2)
    selected = np.sort(rng.choice(eligible, min(len(eligible), config["fold_in_users"]), replace=False))
    actual, predictions, baselines = [], [], []
    demo = None
    for user in selected:
        history = train[np.searchsorted(train_users, user, side="left"):np.searchsorted(train_users, user, side="right")]
        targets = supported_test[np.searchsorted(test_users, user, side="left"):np.searchsorted(test_users, user, side="right")]
        rows = items[history]
        bias, factors = fold_profile(qi, bi, mean, rows, ratings[history], config["fold_in_factors_regularization"], config["fold_in_bias_regularization"])
        predictions.append(predict_items(qi, bi, mean, bias, factors, items[targets]))
        baseline_bias = float(np.sum(ratings[history] - mean - baseline_item_bias[rows])) / (len(history) + config["baseline_user_regularization"])
        baselines.append(np.clip(mean + baseline_bias + baseline_item_bias[items[targets]], .5, 5))
        actual.append(ratings[targets])
        if demo is None and 5 <= len(history) <= 200:
            demo = {"user_row": int(user), "history_indices": history.tolist(), "test_indices": targets[:20].tolist()}
    if not actual:
        raise ValueError("No eligible MovieLens histories remain for deployment-style evaluation.")
    actual = np.concatenate(actual)
    return {
        "users_evaluated": len(selected), "eligible_users": len(eligible),
        "supported_test_ratings": len(supported_test), "all_test_ratings": len(test),
        "svd_fold_in": metrics(actual, np.concatenate(predictions)),
        "regularized_bias_baseline": metrics(actual, np.concatenate(baselines)),
        "history": "training-period ratings only; model user factors are never used for fold-in",
    }, demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "training/collaborative/config.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new output folder; existing model artifacts are not overwritten.")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    prepared = json.loads((args.prepared / "manifest.json").read_text(encoding="utf-8"))
    if prepared["schema_version"] != 1:
        raise ValueError("Unknown prepared dataset schema.")
    for name, checksum in prepared["files"].items():
        if Path(name).name != name or digest(args.prepared / name) != checksum:
            raise ValueError("Prepared dataset checksum mismatch.")
    movies = json.loads((args.prepared / "movies.json").read_text(encoding="utf-8"))
    with np.load(args.prepared / "ratings.npz", allow_pickle=False) as source:
        users, items, ratings, timestamps, movie_lens_users = (source[name] for name in ("users", "items", "ratings", "timestamps", "movielens_user_ids"))
    user_count, item_count = len(movie_lens_users), len(movies)
    if len(ratings) != prepared["matched_rating_count"] or any(len(array) != len(ratings) for array in (users, items, timestamps)) or np.any(np.diff(users) < 0):
        raise ValueError("Prepared rating dimensions/order are invalid.")
    started = time.perf_counter()
    raw_train, validation, test, train_cut, test_cut = temporal_split(timestamps, config["train_fraction"], config["validation_fraction"])
    counts = np.bincount(items[raw_train], minlength=item_count)
    train = raw_train[counts[items[raw_train]] >= config["minimum_item_train_ratings"]]
    del raw_train
    mean, base_bu, base_bi, user_counts, item_counts = baseline(users, items, ratings, train, user_count, item_count, config)
    state = initialize(user_count, item_count, mean, base_bu, base_bi, user_counts, item_counts, config)
    rng = np.random.default_rng(config["seed"] + 1)
    sample = np.sort(rng.choice(validation, min(config["validation_sample_size"], len(validation)), replace=False))
    baseline_validation = metrics(ratings[sample], np.clip(mean + base_bu[users[sample]] + base_bi[items[sample]], .5, 5))
    print(f"Chronological fit: {len(train):,} train, {len(validation):,} validation, {len(test):,} test ratings.", flush=True)
    print(f"Baseline validation RMSE: {baseline_validation['rmse']:.6f}", flush=True)
    best_state, best_score, best_epoch, stale, history = None, float("inf"), 0, 0, []
    for number in range(1, config["max_epochs"] + 1):
        epoch_started = time.perf_counter()
        order = rng.permutation(train).astype(np.int32)
        epoch(users, items, ratings, order, *state, config["learning_rate"] * config["learning_rate_decay"] ** (number - 1), config["regularization"])
        validation_metrics = metrics(ratings[sample], predict(users, items, sample, *state))
        entry = {"epoch": number, **validation_metrics, "seconds": time.perf_counter() - epoch_started}
        history.append(entry)
        print("Validation " + json.dumps(entry), flush=True)
        if validation_metrics["rmse"] < best_score - config["minimum_improvement"]:
            best_score, best_epoch, stale = validation_metrics["rmse"], number, 0
            best_state = tuple(value.copy() if isinstance(value, np.ndarray) else value for value in state)
        else:
            stale += 1
            if stale >= config["patience"]:
                break
    state = best_state
    test_predictions = predict(users, items, test, *state)
    warm = (user_counts[users[test]] > 0) & (item_counts[items[test]] > 0)
    folded, demo = fold_in_evaluation(users, items, ratings, train, test, state, item_counts, base_bi, config)
    evaluation = {
        "rating_scale": [0.5, 5.0], "method": "global chronological split; equal timestamps stay together",
        "train_before_utc": datetime.fromtimestamp(train_cut, timezone.utc).isoformat(),
        "validation_before_utc": datetime.fromtimestamp(test_cut, timezone.utc).isoformat(),
        "train_ratings": len(train), "validation_ratings": len(validation), "test_ratings": len(test),
        "validation_sample_ratings": len(sample), "baseline_validation": baseline_validation,
        "epochs": history, "selected_epoch": best_epoch,
        "all_test": metrics(ratings[test], test_predictions),
        "warm_test": metrics(ratings[test][warm], test_predictions[warm]),
        "warm_test_fraction": float(np.mean(warm)),
        "baseline_test": metrics(ratings[test], np.clip(mean + base_bu[users[test]] + base_bi[items[test]], .5, 5)),
        "global_mean_test": metrics(ratings[test], np.full(len(test), mean)),
        "deployment_style_evaluation": folded,
        "production_refit_after_evaluation": True,
        "metrics_apply_to": "held-out evaluation model before production refit; never an evaluation of test ratings after refitting",
    }
    print("Held-out results " + json.dumps({key: evaluation[key] for key in ("selected_epoch", "all_test", "warm_test", "baseline_test", "deployment_style_evaluation")}), flush=True)
    # The final model includes recent movies from the full authentic dataset.
    # Test metrics above remain those of the untouched, pre-refit holdout.
    full_counts = np.bincount(items, minlength=item_count)
    production = np.flatnonzero(full_counts[items] >= config["minimum_item_train_ratings"])
    del state, best_state, train, validation, test, order, test_predictions
    gc.collect()
    mean, bu, bi, full_user_counts, full_item_counts = baseline(users, items, ratings, production, user_count, item_count, config)
    final_state = initialize(user_count, item_count, mean, bu, bi, full_user_counts, full_item_counts, config)
    rng = np.random.default_rng(config["seed"] + 3)
    for number in range(1, best_epoch + 1):
        order = rng.permutation(production).astype(np.int32)
        epoch(users, items, ratings, order, *final_state, config["learning_rate"] * config["learning_rate_decay"] ** (number - 1), config["regularization"])
        print(f"Production refit epoch {number}/{best_epoch} complete.", flush=True)
    _, qi, _, bi, mean = final_state
    included = np.flatnonzero(full_item_counts >= config["minimum_item_train_ratings"])
    exported_movies = [movies[row] for row in included]
    if not np.all(np.isfinite(qi)) or not np.all(np.isfinite(bi)):
        raise ValueError("Model diverged; refusing to export invalid factors.")
    args.output.mkdir(parents=True)
    np.savez_compressed(args.output / "model.npz", tmdb_ids=np.asarray([movie["tmdb_id"] for movie in exported_movies], dtype=np.int64), item_factors=qi[included], item_bias=bi[included], rating_counts=full_item_counts[included], global_mean=np.asarray(mean))
    write_json(args.output / "movies.json", exported_movies)
    if demo:
        indices = demo["history_indices"]
        evaluation["authentic_demo_profile"] = {
            "source": "MovieLens 32M training-period history", "movielens_user_id": int(movie_lens_users[demo["user_row"]]),
            "ratings": [{"tmdb_id": movies[int(items[index])]["tmdb_id"], "score": int(ratings[index] * 2), "timestamp": int(timestamps[index])} for index in indices],
        }
    write_json(args.output / "evaluation.json", evaluation)
    write_json(args.output / "manifest.json", {
        "format_version": 1, "engine": ENGINE, "created_at": datetime.now(timezone.utc).isoformat(),
        "catalog_sha256": prepared["catalog_sha256"], "source_archive_sha256": prepared["source_archive_sha256"],
        "prepared_manifest_sha256": digest(args.prepared / "manifest.json"), "config": config,
        "movie_count": len(exported_movies), "user_count": int(np.count_nonzero(full_user_counts)), "training_ratings": len(production),
        "catalog_movie_count": prepared["catalog_movie_count"], "catalog_coverage": len(exported_movies) / prepared["catalog_movie_count"],
        "selected_epochs": best_epoch, "build_seconds": time.perf_counter() - started,
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "numba": numba.__version__},
        "files": {name: digest(args.output / name) for name in DATA_FILES},
    })
    print(f"Exported production SVD: {len(exported_movies)} movies, {len(production):,} real ratings, {best_epoch} epochs.", flush=True)


if __name__ == "__main__":
    main()
