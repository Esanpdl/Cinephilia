"""Composition only: existing content and collaborative models remain immutable."""
from collections.abc import Mapping
from dataclasses import dataclass
import math


COMPONENTS = ("content", "collaborative", "popularity")


@dataclass(frozen=True)
class HybridScore:
    tmdb_id: int
    score: float
    components: dict
    effective_weights: dict


class HybridService:
    def __init__(self, content, collaborative, weights, minimum_liked_rating=7, max_seeds=20):
        if set(weights) != set(COMPONENTS) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()):
            raise ValueError("Hybrid weights must be finite, nonnegative content/collaborative/popularity values.")
        if weights["popularity"] <= 0:
            raise ValueError("Keep a positive popularity weight for cold-start fallback.")
        if type(minimum_liked_rating) is not int or not 1 <= minimum_liked_rating <= 10 or type(max_seeds) is not int or not 1 <= max_seeds <= 100:
            raise ValueError("Invalid content profile configuration.")
        total = sum(weights.values())
        self.weights = {name: float(value / total) for name, value in weights.items()}
        self.content, self.collaborative = content, collaborative
        self.minimum_liked_rating, self.max_seeds = minimum_liked_rating, max_seeds

    def rank(self, history, catalog, exclude_ids=()):
        if not isinstance(history, Mapping) or any(type(key) is not int or key <= 0 or type(value) is not int or not 1 <= value <= 10 for key, value in history.items()):
            raise ValueError("History must map positive TMDB IDs to integer 1-10 ratings.")
        blocked = set(history) | set(exclude_ids)
        if any(type(key) is not int or key <= 0 for key in blocked):
            raise ValueError("Excluded IDs must be positive integers.")
        if len({entry["tmdb_id"] for entry in catalog}) != len(catalog):
            raise ValueError("Catalog has duplicate TMDB IDs.")
        candidates = [entry["tmdb_id"] for entry in catalog if entry["tmdb_id"] not in blocked]
        seeds = []
        if self.content is not None and self.weights["content"]:
            # Stable sort retains recency order supplied by the database for ties.
            seeds = sorted(((key, score) for key, score in history.items() if score >= self.minimum_liked_rating and self.content.contains(key)), key=lambda entry: -entry[1])[:self.max_seeds]
        content_scores = dict.fromkeys(candidates)
        if seeds:
            covered = [key for key in candidates if self.content.contains(key)]
            values = dict.fromkeys(covered, 0.0)
            strength = sum(score - self.minimum_liked_rating + 1 for _, score in seeds)
            for seed, rating in seeds:
                scores = self.content.score_candidates(seed, covered)
                weight = (rating - self.minimum_liked_rating + 1) / strength
                for key in covered:
                    values[key] += weight * scores[key]
            maximum = max(values.values(), default=0)
            content_scores.update({key: min(1.0, max(0.0, value / maximum)) if maximum > 0 else 0.0 for key, value in values.items()})
        cf = self.collaborative if self.weights["collaborative"] else None
        cf_status = cf.profile_status(history) if cf is not None else {"available": False, "known_ratings": 0}
        cf_scores = cf.score_candidates(history, candidates) if cf is not None else dict.fromkeys(candidates)
        popularities = {}
        for entry in catalog:
            value = float(entry["popularity"])
            if not math.isfinite(value) or value < 0:
                raise ValueError("Catalog contains invalid TMDB popularity.")
            popularities[entry["tmdb_id"]] = math.log1p(value)
        maximum = max(popularities.values(), default=0)
        results = []
        for key in candidates:
            components = {"content": content_scores[key], "collaborative": cf_scores[key].normalized_score if cf_scores[key] is not None else None, "popularity": popularities[key] / maximum if maximum > 0 else 0.0}
            available = sum(self.weights[name] for name in COMPONENTS if components[name] is not None)
            effective = {name: self.weights[name] / available if components[name] is not None else 0.0 for name in COMPONENTS}
            score = sum(effective[name] * (components[name] or 0.0) for name in COMPONENTS)
            if not math.isfinite(score) or not 0 <= score <= 1.00000001:
                raise ValueError("A component returned an invalid hybrid score.")
            results.append(HybridScore(key, min(score, 1.0), components, effective))
        results.sort(key=lambda entry: (-entry.score, entry.tmdb_id))
        profile = {"rated_movies": len(history), "content_seed_count": len(seeds), "collaborative_history_count": cf_status["known_ratings"], "collaborative_available": cf_status["available"], "mode": "hybrid" if seeds and cf_status["available"] else "content" if seeds else "collaborative" if cf_status["available"] else "popularity"}
        return results, profile
