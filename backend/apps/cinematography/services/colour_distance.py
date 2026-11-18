"""All-frame perceptual distribution comparison, independent of display palettes."""
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy.spatial.distance import cdist

VERSION = 'lab-chroma-sliced-wasserstein-v1'
QUANTILES = 64
directions = np.vstack([np.eye(3), np.random.default_rng(812).normal(size=(9, 3))])
DIRECTIONS = directions / np.linalg.norm(directions, axis=1, keepdims=True)
DIMENSIONS = (len(DIRECTIONS) + 1) * QUANTILES
DISTANCE_SCALE = 12.0  # Lab units; a fixed similarity scale, not an accuracy calibration.


def signature(points, weights):
    points, weights = np.asarray(points), np.asarray(weights)
    if points.ndim != 2 or points.shape[1] != 3 or weights.shape != (len(points),) or not len(points):
        raise ValueError('Expected weighted Lab colours')
    if not np.isfinite(points).all() or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('Invalid colour distribution')
    targets = (np.arange(QUANTILES) + .5) / QUANTILES
    projected = np.column_stack([points @ DIRECTIONS.T, np.hypot(points[:, 1], points[:, 2])])
    result = []
    for values in projected.T:
        order = np.argsort(values, kind='stable')
        cumulative = np.cumsum(weights[order]) / weights.sum()
        result.extend(values[order][np.minimum(np.searchsorted(cumulative, targets), len(order)-1)])
    return np.asarray(result, dtype=np.float32)


def similarity_matrix(left, right):
    left, right = np.atleast_2d(left), np.atleast_2d(right)
    if left.shape[1] != DIMENSIONS or right.shape[1] != DIMENSIONS or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError('Invalid perceptual colour signatures')
    # Mean 1-D transport distances across Lab directions plus chroma transport.
    # The chroma term resolves neutral/warm colours even at similar lightness.
    lab = cdist(left[:, :-QUANTILES], right[:, :-QUANTILES], 'cityblock') / (DIMENSIONS-QUANTILES)
    chroma = cdist(left[:, -QUANTILES:], right[:, -QUANTILES:], 'cityblock') / QUANTILES
    return np.exp(-(.5 * lab + .5 * chroma) / DISTANCE_SCALE)


@lru_cache(maxsize=512)
def _read(path, modified, film_only=False):
    with np.load(path, allow_pickle=False) as data:
        keys = ('version', 'source_sha256', 'palette_method', 'film') if film_only else data.files
        return {key: data[key] for key in keys}


def load_signature(root, tmdb_id, source_sha256, palette_method, film_only=False):
    path = Path(root) / f'data/still-frame-dataset/colour-signatures/{tmdb_id}.npz'
    try:
        data = _read(str(path), path.stat().st_mtime_ns, film_only)
        if (str(data['version']) != VERSION or str(data['source_sha256']) != source_sha256
                or str(data['palette_method']) != palette_method):
            return None
        if data['film'].shape != (DIMENSIONS,) or (not film_only and data['frames'].shape != (len(data['frame_ids']), DIMENSIONS)):
            return None
        return data
    except (OSError, ValueError, KeyError):
        return None
