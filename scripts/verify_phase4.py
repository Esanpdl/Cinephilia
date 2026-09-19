"""Numerical contracts and authentic-model verification; never fit the dataset locally."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "training/collaborative"))
from apps.recommendations.services.collaborative.artifacts import DATA_FILES, ENGINE, digest, write_json
from apps.recommendations.services.collaborative.contracts import CollaborativeModelError
from apps.recommendations.services.collaborative.engine import SVDService
from validation import temporal_split, validate_config


class CollaborativeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_movies = json.loads((ROOT / "data/collaborative/prepared/movies.json").read_text(encoding="utf-8"))
        with np.load(ROOT / "data/collaborative/prepared/ratings.npz", allow_pickle=False) as source:
            rows, scores = source["items"][:8].copy(), source["ratings"][:8].copy()
        cls.movies = sorted((all_movies[int(row)] for row in rows), key=lambda movie: movie["tmdb_id"])
        cls.real_ratings = {all_movies[int(row)]["tmdb_id"]: int(score * 2) for row, score in zip(rows, scores)}
        cls.ids = [movie["tmdb_id"] for movie in cls.movies]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = json.loads((ROOT / "training/collaborative/config.json").read_text(encoding="utf-8"))
        self.config["factors"] = 2
        # Mathematical parameter fixtures, not a trained model or fabricated data.
        factors = np.column_stack((np.linspace(-.4, .4, 8), np.linspace(.3, -.1, 8))).astype(np.float32)
        np.savez_compressed(self.directory / "model.npz", tmdb_ids=np.asarray(self.ids), item_factors=factors, item_bias=np.linspace(-.3, .3, 8).astype(np.float32), rating_counts=np.full(8, 20, dtype=np.int64), global_mean=np.asarray(3.5))
        write_json(self.directory / "movies.json", self.movies)
        write_json(self.directory / "evaluation.json", {})
        write_json(self.directory / "manifest.json", {"format_version": 1, "engine": ENGINE, "movie_count": 8, "config": self.config, "catalog_sha256": "numerical-test-only", "files": {name: digest(self.directory / name) for name in DATA_FILES}})
        self.service = SVDService(self.directory)
        self.history = {movie_id: self.real_ratings[movie_id] for movie_id in self.ids[:3]}

    def test_profile_matches_independent_augmented_least_squares(self):
        service = self.service
        rows = [service.rows[movie_id] for movie_id in self.history]
        design = np.column_stack((np.ones(len(rows)), service.item_factors[rows].astype(np.float64)))
        target = np.asarray(list(self.history.values())) / 2 - service.mean - service.item_bias[rows]
        regularization = np.diag(np.sqrt([self.config["fold_in_bias_regularization"], *([self.config["fold_in_factors_regularization"]] * 2)]))
        coefficients = np.linalg.lstsq(np.vstack((design, regularization)), np.concatenate((target, np.zeros(3))), rcond=None)[0]
        predictions = service.score_candidates(self.history, self.ids)
        expected = np.clip(service.mean + coefficients[0] + service.item_bias + service.item_factors @ coefficients[1:], .5, 5)
        np.testing.assert_allclose([predictions[movie_id].predicted_rating for movie_id in self.ids], expected * 2, atol=1e-7)
        np.testing.assert_allclose([predictions[movie_id].normalized_score for movie_id in self.ids], (expected - .5) / 4.5, atol=1e-7)

    def test_cold_start_and_unknown_movies_are_explicit(self):
        self.assertEqual(self.service.recommend({}), [])
        self.assertIsNone(self.service.score_candidates(dict(list(self.history.items())[:2]), [self.ids[-1]])[self.ids[-1]])
        self.assertIsNone(self.service.score_candidates(self.history, [2147483647])[2147483647])
        status = self.service.profile_status({**self.history, 2147483647: 8})
        self.assertEqual(status["known_ratings"], 3)
        self.assertEqual(status["ignored_ratings"], 1)

    def test_seen_movies_exclusions_order_and_profile_cache(self):
        matches = self.service.recommend(self.history, 8, [self.ids[-1]])
        self.assertFalse(set(self.history) & {match.tmdb_id for match in matches})
        self.assertNotIn(self.ids[-1], {match.tmdb_id for match in matches})
        self.assertEqual(matches, sorted(matches, key=lambda match: (-match.predicted_rating, match.tmdb_id)))
        again = self.service.recommend(dict(reversed(list(self.history.items()))), 8, [self.ids[-1]])
        self.assertEqual(matches, again)
        self.assertGreater(self.service._profiles.cache_info().hits, 0)

    def test_invalid_inputs(self):
        for value in (True, 0, 11, 2.5, float("nan"), "8"):
            with self.assertRaises(ValueError):
                self.service.recommend({self.ids[0]: value})
        with self.assertRaises(ValueError):
            self.service.recommend(self.history, limit=0)
        with self.assertRaises(ValueError):
            self.service.score_candidates(self.history, [True])

    def test_artifact_tampering_and_failed_activation(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.test.utils import override_settings
        from apps.recommendations.services.collaborative.registry import activate, get_collaborative_service
        pointer = self.directory / "current.json"
        with override_settings(COLLABORATIVE_MODEL_POINTER=pointer):
            activate(self.directory, pointer)
            original = pointer.read_bytes()
            self.assertIs(get_collaborative_service(), get_collaborative_service())
            with (self.directory / "movies.json").open("a", encoding="utf-8") as target:
                target.write(" ")
            with self.assertRaisesRegex(CollaborativeModelError, "checksum mismatch"):
                activate(self.directory, pointer)
            self.assertEqual(original, pointer.read_bytes())

    def test_global_time_split_keeps_ties_and_has_no_future_rows(self):
        timestamps = np.repeat(np.arange(10, 110, 10), 3)
        train, validation, test, cutoff, test_cutoff = temporal_split(timestamps, .6, .2)
        self.assertLess(max(timestamps[train]), min(timestamps[validation]))
        self.assertLess(max(timestamps[validation]), min(timestamps[test]))
        self.assertEqual(len(set(train) | set(validation) | set(test)), len(timestamps))
        self.assertEqual(set(timestamps[train]) & set(timestamps[test]), set())
        validate_config(self.config)
        with self.assertRaises(ValueError):
            temporal_split(np.ones(10), .8, .1)

    def test_sgd_single_step_uses_both_original_factor_values(self):
        # Execute the exact SGD source as Python for one numerical gradient
        # check, with the JIT decorator disabled. No MovieLens model is fitted.
        spec = importlib.util.spec_from_file_location("numerical_sgd", ROOT / "training/collaborative/sgd.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"numba": SimpleNamespace(njit=lambda **_: lambda function: function)}):
            spec.loader.exec_module(module)
        pu, qi = np.asarray([[.2, -.1]]), np.asarray([[.3, .4]])
        bu, bi = np.asarray([.1]), np.asarray([-.1])
        old_pu, old_qi, old_bu, old_bi = pu.copy(), qi.copy(), bu.copy(), bi.copy()
        rating, mean, rate, reg = 4.0, 3.0, .01, .05
        error = rating - (mean + bu[0] + bi[0] + float(pu[0] @ qi[0]))
        module.epoch(np.asarray([0]), np.asarray([0]), np.asarray([rating]), np.asarray([0]), pu, qi, bu, bi, mean, rate, reg)
        np.testing.assert_allclose(pu, old_pu + rate * (error * old_qi - reg * old_pu))
        np.testing.assert_allclose(qi, old_qi + rate * (error * old_pu - reg * old_qi))
        np.testing.assert_allclose(bu, old_bu + rate * (error - reg * old_bu))
        np.testing.assert_allclose(bi, old_bi + rate * (error - reg * old_bi))

    def test_django_user_adapter_queries_site_ratings_only(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from apps.recommendations.services.collaborative.registry import history_for_user
        with patch("apps.ratings.models.Rating.objects.filter") as query:
            query.return_value.values_list.return_value = []
            self.assertEqual(history_for_user(42), {})
            query.assert_called_once_with(user_id=42)
            query.return_value.values_list.assert_called_once_with("movie__tmdb_id", "score")


def verify_artifact(directory):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    started = time.perf_counter()
    service = SVDService(directory)
    load_seconds = time.perf_counter() - started
    catalog = json.loads((ROOT / "data/collaborative/catalog.json").read_text(encoding="utf-8"))
    prepared = json.loads((ROOT / "data/collaborative/prepared/manifest.json").read_text(encoding="utf-8"))
    assert service.manifest["catalog_sha256"] == catalog["catalog_sha256"]
    assert service.manifest["source_archive_sha256"] == prepared["source_archive_sha256"]
    assert service.manifest["prepared_manifest_sha256"] == digest(ROOT / "data/collaborative/prepared/manifest.json")
    catalog_ids = {movie["tmdb_id"] for movie in catalog["movies"]}
    assert set(service.ids) <= catalog_ids
    evaluation = json.loads((directory / "evaluation.json").read_text(encoding="utf-8"))
    demo = evaluation["authentic_demo_profile"]
    history = {entry["tmdb_id"]: entry["score"] for entry in demo["ratings"]}
    assert all(entry["timestamp"] < int(__import__("datetime").datetime.fromisoformat(evaluation["train_before_utc"]).timestamp()) for entry in demo["ratings"])
    with CaptureQueriesContext(connection) as queries:
        matches = service.recommend(history, 20)
        assert matches and not set(history).intersection(match.tmdb_id for match in matches)
        assert all(1 <= match.predicted_rating <= 10 and 0 <= match.normalized_score <= 1 for match in matches)
        direct = service.score_candidates(history, [match.tmdb_id for match in matches])
        assert all(match == direct[match.tmdb_id] for match in matches)
        excluded = [match.tmdb_id for match in matches[:5]]
        assert not set(excluded).intersection(match.tmdb_id for match in service.recommend(history, 20, excluded))
        assert service.recommend({}) == []
        assert len(queries) == 0
    started = time.perf_counter()
    for _ in range(20):
        service.recommend(history, 10)
    report = {
        "movie_count": service.manifest["movie_count"], "training_ratings": service.manifest["training_ratings"],
        "catalog_coverage": service.manifest["catalog_coverage"], "cold_start_explicit": True,
        "inference_db_queries": len(queries), "load_seconds": load_seconds,
        "mean_recommend_ms_20_calls": (time.perf_counter() - started) * 50,
        "artifact_bytes": sum(path.stat().st_size for path in directory.iterdir() if path.is_file()),
        "demo_source": {"dataset": demo["source"], "movielens_user_id": demo["movielens_user_id"], "ratings": len(history)},
        "demo_recommendations": [{"tmdb_id": match.tmdb_id, "title": service.movie(match.tmdb_id)["title"], "predicted_rating": match.predicted_rating} for match in matches[:10]],
        "test_metrics": {key: evaluation[key] for key in ("all_test", "baseline_test", "deployment_style_evaluation")},
    }
    write_json(ROOT / "data/collaborative/verification.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CollaborativeContracts))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.artifact:
        verify_artifact(args.artifact)
