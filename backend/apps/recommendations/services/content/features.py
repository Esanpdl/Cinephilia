"""Fit weighted TF-IDF metadata blocks for the offline index build."""
import math

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .metadata import FIELDS, identities


def validate_config(config):
    weights = config.get("weights", {})
    if set(weights) != set(FIELDS) or any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Provide finite nonnegative weights for all five fields, with a positive total.")
    for name in ("max_cast", "overview_max_features", "overview_min_df", "neighbors_per_movie", "similarity_batch_size"):
        if type(config.get(name)) is not int or config[name] <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if not 0 < config.get("overview_max_df", 0) <= 1:
        raise ValueError("overview_max_df must be in (0, 1].")


def fit_features(movies, config):
    validate_config(config)
    blocks = []
    vocabulary = {}
    spans = {}
    cursor = 0
    for field in FIELDS:
        if field == "overview":
            documents = [movie["overview"] or "" for movie in movies]
            vectorizer = TfidfVectorizer(
                stop_words="english", strip_accents="unicode", ngram_range=(1, 2),
                max_features=config["overview_max_features"], min_df=config["overview_min_df"],
                max_df=config["overview_max_df"], sublinear_tf=True, dtype=np.float32,
            )
        else:
            # Preserve whole entities with TMDB IDs; names such as "De Niro" are
            # never broken into unrelated words or confused with another person.
            documents = [" ".join(f"{field}:{identifier}" for identifier in sorted(identities(movie, field, config["max_cast"]))) for movie in movies]
            vectorizer = TfidfVectorizer(token_pattern=r"(?u)\S+", lowercase=False, binary=True, dtype=np.float32)
        try:
            block = vectorizer.fit_transform(documents).tocsr()
            names = vectorizer.get_feature_names_out().tolist()
        except ValueError as error:
            if not any(message in str(error) for message in ("empty vocabulary", "After pruning, no terms remain", "max_df corresponds to < documents than min_df")):
                raise
            block = sparse.csr_matrix((len(movies), 0), dtype=np.float32)
            names = []
        # sqrt(weight) makes each block's dot-product contribution proportional
        # to weight, rather than inadvertently squaring the intended weight.
        block = block * np.float32(math.sqrt(config["weights"][field]))
        spans[field] = [cursor, cursor + block.shape[1]]
        cursor += block.shape[1]
        blocks.append(block)
        vocabulary[field] = names
    matrix = sparse.hstack(blocks, format="csr", dtype=np.float32)
    matrix.eliminate_zeros()
    if matrix.shape[1] == 0 or matrix.nnz == 0:
        raise ValueError("No usable content features remain in this catalog/configuration.")
    matrix = normalize(matrix, norm="l2", copy=False).tocsr()
    matrix.eliminate_zeros()
    matrix.sort_indices()
    return matrix, {"fields": spans, "vocabulary": vocabulary}
