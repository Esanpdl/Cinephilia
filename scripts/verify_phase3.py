"""Numerical contract tests and optional verification of a real trained index.

The numerical fixtures below are matrices, not invented movie metadata, and do
not fit/train a model. Metadata is taken unchanged from the authentic snapshot.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.content.artifacts import DATA_FILES, ENGINE_VERSION, FORMAT_VERSION, sha256_file, write_json
from apps.recommendations.services.content.contracts import ContentIndexError, MovieNotIndexed
from apps.recommendations.services.content.engine import TfidfContentService
from apps.recommendations.services.content.metadata import FIELDS
from apps.recommendations.services.content.ranking import build_neighbors, rank_scores


class NumericalContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = json.loads((ROOT / "data/content/catalog.json").read_text(encoding="utf-8"))
        cls.movies = snapshot["movies"][:4]
        cls.ids = np.asarray([movie["tmdb_id"] for movie in cls.movies])
        # Rows 1 and 2 tie against row 0; row 3 has no usable features.
        cls.matrix = sparse.csr_matrix(np.asarray([[1, 0], [.8, .6], [.8, .6], [0, 0]], dtype=np.float32))
        cls.snapshot = snapshot

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        indices, scores = build_neighbors(self.matrix, self.ids, 1, 2, progress=lambda _: None)
        sparse.save_npz(self.directory / "features.npz", self.matrix)
        np.savez_compressed(self.directory / "neighbors.npz", indices=indices, scores=scores)
        write_json(self.directory / "movies.json", self.movies)
        write_json(self.directory / "feature_schema.json", {
            "fields": {field: ([0, 2] if field == "overview" else [2, 2]) for field in FIELDS},
            "vocabulary": {field: (["axis0", "axis1"] if field == "overview" else []) for field in FIELDS},
        })
        self.manifest = {
            "format_version": FORMAT_VERSION, "engine": ENGINE_VERSION,
            "movie_count": 4, "feature_count": 2, "neighbor_count": 1,
            "catalog_sha256": self.snapshot["catalog_sha256"], "config": {"max_cast": 10},
            "files": {name: sha256_file(self.directory / name) for name in DATA_FILES},
        }
        write_json(self.directory / "manifest.json", self.manifest)
        self.service = TfidfContentService(self.directory)

    def test_ties_self_exclusion_and_cache_fallback(self):
        source, first, second, _ = map(int, self.ids)
        self.assertEqual([m.tmdb_id for m in self.service.similar(source, 2)], [first, second])
        self.assertEqual([m.tmdb_id for m in self.service.similar(source, 1, [first])], [second])
        self.assertEqual(self.service.similar(source, 10, [first, second]), [])
        self.assertGreater(self.service._cached_results.cache_info().hits, 0)

    def test_candidate_scores_zero_vectors_and_unknown_ids(self):
        source, first, _, empty = map(int, self.ids)
        values = self.service.score_candidates(source, [source, first, empty, 2147483647, first])
        self.assertAlmostEqual(values[source], 1)
        self.assertAlmostEqual(values[first], .8, places=6)
        self.assertEqual(values[empty], 0)
        self.assertEqual(values[2147483647], 0)
        self.assertEqual(self.service.similar(empty), [])
        with self.assertRaises(MovieNotIndexed):
            self.service.similar(2147483647)
        for invalid in (True, "238", -1):
            with self.assertRaises(ValueError):
                self.service.similar(invalid)

    def test_explanations_sum_to_similarity(self):
        source, first = map(int, self.ids[:2])
        explanation = self.service.explain(source, first)
        self.assertAlmostEqual(sum(explanation["contributions"].values()), explanation["score"], places=6)
        self.assertAlmostEqual(explanation["score"], .8, places=6)

    def test_checksum_failure_is_explicit(self):
        with (self.directory / "movies.json").open("a", encoding="utf-8") as file:
            file.write(" ")
        with self.assertRaisesRegex(ContentIndexError, "checksum mismatch"):
            TfidfContentService(self.directory)

    def test_invalid_neighbor_rejected_even_with_updated_checksum(self):
        indices = np.zeros((4, 1), dtype=np.int32)
        np.savez_compressed(self.directory / "neighbors.npz", indices=indices, scores=np.ones((4, 1), dtype=np.float32))
        self.manifest["files"]["neighbors.npz"] = sha256_file(self.directory / "neighbors.npz")
        write_json(self.directory / "manifest.json", self.manifest)
        with self.assertRaisesRegex(ContentIndexError, "self-matches"):
            TfidfContentService(self.directory)

    def test_activation_caches_service_and_preserves_pointer_on_failure(self):
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.test.utils import override_settings
        from apps.recommendations.services.content.registry import activate, get_content_service
        pointer = self.directory / "current.json"
        with override_settings(CONTENT_INDEX_POINTER=pointer):
            with self.assertRaises(ContentIndexError):
                get_content_service()
            activate(self.directory, pointer)
            original = pointer.read_bytes()
            self.assertIs(get_content_service(), get_content_service())
            with self.assertRaises(ContentIndexError):
                activate(self.directory / "missing", pointer)
            self.assertEqual(pointer.read_bytes(), original)

    def test_batched_cache_matches_dense_reference(self):
        indices, scores = build_neighbors(self.matrix, self.ids, 3, 2, progress=lambda _: None)
        dense = (self.matrix @ self.matrix.T).toarray()
        for row, values in enumerate(dense):
            expected = sorted((j for j in range(4) if j != row and values[j] > 0), key=lambda j: (-values[j], self.ids[j]))
            actual = indices[row][indices[row] >= 0]
            np.testing.assert_array_equal(actual, expected)
            np.testing.assert_allclose(scores[row, :len(expected)], values[expected], atol=1e-6)
        empty, _ = rank_scores(np.asarray([1.0]), np.asarray([1]), 0)
        self.assertEqual(len(empty), 0)


def verify_artifact(directory):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    started = time.perf_counter()
    service = TfidfContentService(directory)
    load_seconds = time.perf_counter() - started
    snapshot = json.loads((ROOT / "data/content/catalog.json").read_text(encoding="utf-8"))
    assert service.manifest["catalog_sha256"] == snapshot["catalog_sha256"]
    assert service.movies == snapshot["movies"]
    rows = sorted(set(np.linspace(0, len(service.movies) - 1, 30, dtype=int).tolist() + [service.rows[238]]))
    with CaptureQueriesContext(connection) as queries:
        for row in rows:
            source = int(service.movie_ids[row])
            # Independent full sort validates both precomputed and fallback paths.
            values = (service.matrix[row] @ service.matrix.T).toarray().ravel()
            expected = sorted((j for j in range(len(values)) if j != row and values[j] > 0), key=lambda j: (-values[j], service.movie_ids[j]))
            for count in (10, 100, 110):
                actual = service.similar(source, count)
                assert [m.tmdb_id for m in actual] == [int(service.movie_ids[j]) for j in expected[:count]]
                np.testing.assert_allclose([m.score for m in actual], values[expected[:count]], atol=1e-6)
            excluded = [int(service.movie_ids[j]) for j in expected[:100]]
            actual = service.similar(source, 10, excluded)
            assert [m.tmdb_id for m in actual] == [int(service.movie_ids[j]) for j in expected[100:110]]
            if expected:
                target = int(service.movie_ids[expected[0]])
                explanation = service.explain(source, target)
                assert abs(sum(explanation["contributions"].values()) - values[expected[0]]) < 1e-5
                assert abs(service.score_candidates(source, [target])[target] - values[expected[0]]) < 1e-5
            # For each nonempty field, squared block norm equals its share of
            # the weights present in this movie after final normalization.
            block_norms = {field: float(service.matrix[row, start:end].multiply(service.matrix[row, start:end]).sum()) for field, (start, end) in service.schema["fields"].items()}
            active_weight = sum(service.manifest["config"]["weights"][field] for field, value in block_norms.items() if value > 0)
            for field, value in block_norms.items():
                if value > 0:
                    assert abs(value - service.manifest["config"]["weights"][field] / active_weight) < 1e-5
        assert len(queries) == 0
    started = time.perf_counter()
    for _ in range(100):
        service.similar(238, 10)
    cached_ms = (time.perf_counter() - started) * 10
    report = {
        "catalog_sha256": service.manifest["catalog_sha256"], "movie_count": len(service.movies),
        "sampled_rows_verified": len(rows), "inference_db_queries": len(queries),
        "load_seconds": load_seconds, "mean_cached_lookup_ms_100_calls": cached_ms,
        "artifact_bytes": sum(path.stat().st_size for path in directory.iterdir() if path.is_file()),
        "godfather_neighbors": [{"tmdb_id": m.tmdb_id, "title": service.movie(m.tmdb_id)["title"], "score": m.score} for m in service.similar(238, 10)],
    }
    write_json(ROOT / "data/content/verification.json", report)
    print(f"Real artifact verified: {len(service.movies)} authentic movies; {len(rows)} rows match exact full-sort rankings; zero inference DB queries.")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NumericalContracts))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.artifact:
        verify_artifact(args.artifact)
