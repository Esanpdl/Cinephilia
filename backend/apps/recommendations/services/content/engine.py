"""Read-only content inference from a previously built, verified sparse index."""
from functools import lru_cache
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from .artifacts import read_manifest
from .contracts import ContentIndexError, MovieNotIndexed, SimilarMovie
from .metadata import FIELDS, identities
from .ranking import rank_scores


def valid_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError("TMDB IDs must be positive integers.")
    return value


class TfidfContentService:
    def __init__(self, directory):
        self.directory = Path(directory)
        try:
            self.manifest = read_manifest(self.directory)
            self.movies = json.loads((self.directory / "movies.json").read_text(encoding="utf-8"))
            self.schema = json.loads((self.directory / "feature_schema.json").read_text(encoding="utf-8"))
            self.matrix = sparse.load_npz(self.directory / "features.npz").tocsr()
            with np.load(self.directory / "neighbors.npz", allow_pickle=False) as stored:
                self.neighbors = stored["indices"]
                self.neighbor_scores = stored["scores"]
            self.movie_ids = np.asarray([valid_id(movie["tmdb_id"]) for movie in self.movies], dtype=np.int64)
            self._validate()
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ContentIndexError(f"Cannot load content index: {error}") from error
        self.rows = {int(movie_id): row for row, movie_id in enumerate(self.movie_ids)}
        for array in (self.matrix.data, self.matrix.indices, self.matrix.indptr, self.neighbors, self.neighbor_scores, self.movie_ids):
            array.setflags(write=False)
        self._cached_results = lru_cache(maxsize=256)(self._calculate_all)

    def _validate(self):
        count = self.manifest["movie_count"]
        if len(self.movies) != count or count == 0 or np.any(np.diff(self.movie_ids) <= 0):
            raise ValueError("Movie IDs are missing, duplicated or unsorted.")
        if self.matrix.shape != (count, self.manifest["feature_count"]):
            raise ValueError("Feature matrix dimensions do not match the manifest.")
        expected = (count, self.manifest["neighbor_count"])
        if self.neighbors.shape != expected or self.neighbor_scores.shape != expected or not np.issubdtype(self.neighbors.dtype, np.integer):
            raise ValueError("Cached neighbor dimensions or index types are invalid.")
        if not np.all(np.isfinite(self.matrix.data)) or np.any(self.matrix.data < 0) or not np.all(np.isfinite(self.neighbor_scores)) or np.any(self.neighbor_scores < 0) or np.any(self.neighbor_scores > 1.00001):
            raise ValueError("Content vectors or similarity scores are invalid.")
        if np.any(self.neighbors < -1) or np.any(self.neighbors >= count) or np.any(self.neighbors == np.arange(count)[:, None]):
            raise ValueError("Neighbor cache contains invalid indices or self-matches.")
        if np.any((self.neighbors == -1) != (self.neighbor_scores == 0)) or np.any(np.diff(self.neighbor_scores, axis=1) > 0):
            raise ValueError("Neighbor cache has inconsistent padding or score order.")
        for row in self.neighbors:
            valid = row[row >= 0]
            if len(np.unique(valid)) != len(valid):
                raise ValueError("Neighbor cache contains duplicate matches.")
        if set(self.schema["fields"]) != set(FIELDS):
            raise ValueError("Feature schema must contain all five metadata fields.")
        cursor = 0
        for field in FIELDS:
            start, end = self.schema["fields"][field]
            if start != cursor or end < start or len(self.schema["vocabulary"][field]) != end - start:
                raise ValueError("Feature column spans are inconsistent.")
            cursor = end
        if cursor != self.matrix.shape[1]:
            raise ValueError("Feature schema does not cover the matrix.")
        norms = np.sqrt(np.asarray(self.matrix.multiply(self.matrix).sum(axis=1)).ravel())
        if np.any((norms > 0) & (np.abs(norms - 1) > 1e-4)):
            raise ValueError("Content feature vectors are not L2-normalized.")

    def _row(self, tmdb_id):
        valid_id(tmdb_id)
        if tmdb_id not in self.rows:
            raise MovieNotIndexed(f"TMDB movie {tmdb_id} is not in this content index. Rebuild after catalog changes.")
        return self.rows[tmdb_id]

    def _calculate_all(self, row):
        values = (self.matrix[row] @ self.matrix.T).toarray().ravel()
        rows, scores = rank_scores(values, self.movie_ids, len(self.movies), blocked_rows=(row,))
        return tuple(SimilarMovie(int(self.movie_ids[index]), float(score)) for index, score in zip(rows, scores))

    def similar(self, tmdb_id, limit=10, exclude_ids=()):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000.")
        row = self._row(tmdb_id)
        excluded = {valid_id(movie_id) for movie_id in exclude_ids} | {tmdb_id}
        cached = [SimilarMovie(int(self.movie_ids[index]), float(score)) for index, score in zip(self.neighbors[row], self.neighbor_scores[row]) if index >= 0 and score > 0 and int(self.movie_ids[index]) not in excluded]
        if len(cached) >= limit or self.neighbors.shape[1] == len(self.movies) - 1:
            return cached[:limit]
        return [match for match in self._cached_results(row) if match.tmdb_id not in excluded][:limit]

    def score_candidates(self, tmdb_id, candidate_ids):
        row = self._row(tmdb_id)
        candidates = list(dict.fromkeys(valid_id(movie_id) for movie_id in candidate_ids))
        result = dict.fromkeys(candidates, 0.0)
        known = [movie_id for movie_id in candidates if movie_id in self.rows]
        if known:
            values = (self.matrix[[self.rows[movie_id] for movie_id in known]] @ self.matrix[row].T).toarray().ravel()
            result.update({movie_id: float(np.clip(score, 0, 1)) for movie_id, score in zip(known, values)})
        return result

    def movie(self, tmdb_id):
        return self.movies[self._row(tmdb_id)]

    def contains(self, tmdb_id):
        valid_id(tmdb_id)
        return tmdb_id in self.rows

    def explain(self, source_id, target_id):
        source_row, target_row = self._row(source_id), self._row(target_id)
        product = self.matrix[source_row].multiply(self.matrix[target_row]).tocsr()
        contributions = {field: float(product[:, start:end].sum()) for field, (start, end) in self.schema["fields"].items()}
        shared = {}
        for field in FIELDS[1:]:
            left = identities(self.movies[source_row], field, self.manifest["config"]["max_cast"])
            right = identities(self.movies[target_row], field, self.manifest["config"]["max_cast"])
            shared[field] = [left[identifier] for identifier in sorted(left.keys() & right.keys())]
        start, end = self.schema["fields"]["overview"]
        overview = product[:, start:end]
        terms = sorted(zip(overview.indices, overview.data), key=lambda entry: (-entry[1], entry[0]))[:8]
        return {
            "score": float(np.clip(product.sum(), 0, 1)), "contributions": contributions,
            "shared": shared,
            "shared_overview_terms": [{"term": self.schema["vocabulary"]["overview"][int(column)], "contribution": float(value)} for column, value in terms],
        }
