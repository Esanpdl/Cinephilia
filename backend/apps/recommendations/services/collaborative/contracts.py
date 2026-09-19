from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


class CollaborativeModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollaborativeScore:
    tmdb_id: int
    predicted_rating: float  # Cinephilia's 1–10 scale.
    normalized_score: float  # 0–1, for the later hybrid engine.
    history_count: int


class CollaborativeFiltering(Protocol):
    def score_candidates(self, history: Mapping[int, int], candidate_ids: Iterable[int]) -> dict[int, CollaborativeScore | None]: ...

    def recommend(self, history: Mapping[int, int], limit: int = 10, exclude_ids: Iterable[int] = ()) -> list[CollaborativeScore]: ...
