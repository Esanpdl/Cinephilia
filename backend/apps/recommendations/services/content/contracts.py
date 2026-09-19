"""No Django dependency: alternative content engines implement the same contract."""
from dataclasses import dataclass
from typing import Iterable, Protocol


class ContentIndexError(RuntimeError):
    pass


class MovieNotIndexed(ContentIndexError):
    pass


@dataclass(frozen=True)
class SimilarMovie:
    tmdb_id: int
    score: float


class ContentSimilarity(Protocol):
    def contains(self, tmdb_id: int) -> bool: ...

    def similar(self, tmdb_id: int, limit: int = 10, exclude_ids: Iterable[int] = ()) -> list[SimilarMovie]: ...

    def score_candidates(self, tmdb_id: int, candidate_ids: Iterable[int]) -> dict[int, float]: ...
