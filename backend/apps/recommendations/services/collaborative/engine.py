from collections.abc import Mapping
from functools import lru_cache
import json
from numbers import Real
from pathlib import Path

import numpy as np

from .artifacts import read_manifest
from .contracts import CollaborativeModelError, CollaborativeScore
from .math import fold_profile, predict_items


def valid_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError("TMDB IDs must be positive integers.")
    return value


class SVDService:
    """Fixed MovieLens movie factors, personalized from the site's own ratings.

    This service never accepts a MovieLens/Django user ID as a model row index.
    Unknown movies and insufficient history explicitly yield no CF prediction.
    """

    def __init__(self, directory):
        self.directory = Path(directory)
        try:
            self.manifest = read_manifest(self.directory)
            self.movies = json.loads((self.directory / "movies.json").read_text(encoding="utf-8"))
            self.config = self.manifest["config"]
            with np.load(self.directory / "model.npz", allow_pickle=False) as stored:
                self.ids = stored["tmdb_ids"]
                self.item_factors = stored["item_factors"]
                self.item_bias = stored["item_bias"]
                self.support = stored["rating_counts"]
                self.mean = float(stored["global_mean"].item())
            count, factors = self.manifest["movie_count"], self.config["factors"]
            if count < 1 or self.ids.shape != (count,) or not np.issubdtype(self.ids.dtype, np.integer) or np.any(self.ids <= 0) or np.any(np.diff(self.ids) <= 0):
                raise ValueError("Invalid or unsorted collaborative movie IDs.")
            if self.item_factors.shape != (count, factors) or self.item_bias.shape != (count,) or self.support.shape != (count,):
                raise ValueError("Collaborative factor dimensions are inconsistent.")
            if not np.issubdtype(self.support.dtype, np.integer) or np.any(self.support < self.config["minimum_item_train_ratings"]):
                raise ValueError("Collaborative item support is invalid.")
            if not np.all(np.isfinite(self.item_factors)) or not np.all(np.isfinite(self.item_bias)) or not .5 <= self.mean <= 5:
                raise ValueError("Collaborative model contains invalid values.")
            if [valid_id(movie["tmdb_id"]) for movie in self.movies] != self.ids.tolist():
                raise ValueError("Collaborative metadata does not match model rows.")
            if any(not isinstance(self.config.get(key), (float, int)) or not np.isfinite(self.config[key]) or self.config[key] <= 0 for key in ("fold_in_factors_regularization", "fold_in_bias_regularization", "minimum_history")):
                raise ValueError("Invalid collaborative profile configuration.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CollaborativeModelError(f"Cannot load collaborative model: {error}") from error
        self.rows = {int(movie_id): row for row, movie_id in enumerate(self.ids)}
        for array in (self.ids, self.item_factors, self.item_bias, self.support):
            array.setflags(write=False)
        self._profiles = lru_cache(maxsize=128)(self._fold)

    def _history(self, history):
        if not isinstance(history, Mapping):
            raise ValueError("history must map TMDB IDs to integer ratings on the 1–10 scale.")
        normalized = []
        for movie_id, score in history.items():
            valid_id(movie_id)
            if isinstance(score, bool) or not isinstance(score, Real) or not np.isfinite(score) or score != int(score) or not 1 <= score <= 10:
                raise ValueError("History ratings must be integers from 1 to 10.")
            if movie_id in self.rows:
                normalized.append((movie_id, int(score)))
        return tuple(sorted(normalized))

    def _fold(self, key):
        rows = np.asarray([self.rows[movie_id] for movie_id, _ in key])
        ratings = np.asarray([score / 2 for _, score in key])
        return fold_profile(self.item_factors, self.item_bias, self.mean, rows, ratings, self.config["fold_in_factors_regularization"], self.config["fold_in_bias_regularization"])

    def profile_status(self, history):
        key = self._history(history)
        return {"available": len(key) >= self.config["minimum_history"], "known_ratings": len(key), "ignored_ratings": len(history) - len(key), "minimum_history": self.config["minimum_history"]}

    def score_candidates(self, history, candidate_ids):
        key = self._history(history)
        candidates = list(dict.fromkeys(valid_id(movie_id) for movie_id in candidate_ids))
        result = dict.fromkeys(candidates)
        if len(key) < self.config["minimum_history"]:
            return result
        supported = [movie_id for movie_id in candidates if movie_id in self.rows]
        if supported:
            bias, factors = self._profiles(key)
            rows = np.asarray([self.rows[movie_id] for movie_id in supported])
            predictions = predict_items(self.item_factors, self.item_bias, self.mean, bias, factors, rows)
            result.update({movie_id: CollaborativeScore(movie_id, float(score * 2), float((score - .5) / 4.5), len(key)) for movie_id, score in zip(supported, predictions)})
        return result

    def recommend(self, history, limit=10, exclude_ids=()):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000.")
        excluded = {valid_id(movie_id) for movie_id in exclude_ids} | set(history)
        predictions = self.score_candidates(history, (int(movie_id) for movie_id in self.ids if int(movie_id) not in excluded))
        return sorted((score for score in predictions.values() if score is not None), key=lambda score: (-score.predicted_rating, score.tmdb_id))[:limit]

    def movie(self, tmdb_id):
        valid_id(tmdb_id)
        if tmdb_id not in self.rows:
            raise KeyError(f"TMDB movie {tmdb_id} has no collaborative factor in this artifact.")
        return self.movies[self.rows[tmdb_id]]
