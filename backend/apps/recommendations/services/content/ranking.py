"""Exact deterministic cosine ranking and bounded-memory neighbor precomputation."""
import numpy as np


def rank_scores(scores, movie_ids, limit, blocked_rows=()):
    scores = np.asarray(scores).reshape(-1).copy()
    if limit <= 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=scores.dtype)
    if blocked_rows:
        scores[list(blocked_rows)] = -1
    eligible = np.flatnonzero(scores > 0)
    if len(eligible) > limit:
        threshold = np.partition(scores[eligible], len(eligible) - limit)[len(eligible) - limit]
        eligible = eligible[scores[eligible] >= threshold]
    order = np.lexsort((movie_ids[eligible], -scores[eligible]))
    rows = eligible[order[:limit]]
    return rows, np.clip(scores[rows], 0, 1)


def build_neighbors(matrix, movie_ids, count, batch_size, progress=print):
    size = len(movie_ids)
    width = min(count, max(0, size - 1))
    indices = np.full((size, width), -1, dtype=np.int32)
    scores = np.zeros((size, width), dtype=np.float32)
    for start in range(0, size, batch_size):
        end = min(start + batch_size, size)
        # Only batch_size x N is dense; the N x N similarity matrix is not stored.
        block = (matrix[start:end] @ matrix.T).toarray()
        for offset, values in enumerate(block):
            row = start + offset
            ranked, similarities = rank_scores(values, movie_ids, width, blocked_rows=(row,))
            indices[row, :len(ranked)] = ranked
            scores[row, :len(ranked)] = similarities
        progress(f"Computed neighbor rows {end}/{size}")
    return indices, scores
