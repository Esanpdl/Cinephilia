"""Pair visible frames using equal colour and published framing contributions."""
from functools import lru_cache
import json
import numpy as np
from scipy.optimize import linear_sum_assignment
from django.conf import settings
from .colour_distance import load_signature, similarity_matrix

VERSION = 'frame-lab-8x8x8-v2'
SHOT_SCALES = ('extreme_close_up', 'close_up', 'medium_close_up', 'medium', 'full', 'wide')
COMPOSITION = frozenset(('symmetry', 'negative-space', 'frame-within-frame', 'deep-staging'))


def framing_similarity(left, right):
    """Use published evidence only. Missing labels do not establish agreement."""
    a, b = (frame.get('technique_analysis') or {} for frame in (left, right))
    if any(item.get('source') not in ('human', 'model') for item in (a, b)):
        return 0.0
    signals = []
    shots = [item.get('shot_scale') for item in (a, b)]
    if all(shot in SHOT_SCALES for shot in shots):
        signals.append(1 - abs(SHOT_SCALES.index(shots[0]) - SHOT_SCALES.index(shots[1])) / 5)
    tags = [set(item.get('tags', [])) & COMPOSITION for item in (a, b)]
    if all(tags):
        signals.append(len(tags[0] & tags[1]) / len(tags[0] | tags[1]))
    return float(np.mean(signals)) if signals else 0.0


def combined_scores(colours, left, right):
    framing = np.asarray([[framing_similarity(a, b) for b in right] for a in left])
    return .5 * colours + .5 * framing


@lru_cache(maxsize=64)
def _read(path, modified_ns):
    return json.loads(path.read_text('utf-8'))


def histograms(analysis):
    path = settings.BASE_DIR.parent / f'data/still-frame-dataset/frame-matching/{analysis.movie.tmdb_id}.json'
    try:
        data = _read(path, path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return {}
    if (data.get('version') != VERSION or data.get('source_sha256') != analysis.source_sha256
            or data.get('palette_version') != analysis.quality.get('palette_method')):
        return {}
    return data['frames']


def top_pairs(scores, limit=10):
    """Maximum-total-similarity assignment of exactly k distinct pairs."""
    n, m = scores.shape
    k = min(limit, n, m)
    if not k:
        return []
    # Dummy assignments account for all unused frames. Dummy-to-dummy is forbidden.
    cost = np.zeros((n + m - k, m + n - k))
    cost[:n, :m] = -scores
    cost[n:, m:] = 1e6
    left, right = linear_sum_assignment(cost)
    pairs = [(int(i), int(j), float(scores[i, j])) for i, j in zip(left, right) if i < n and j < m]
    return sorted(pairs, key=lambda row: (-row[2], row[0], row[1]))


def matched_frames(left, right):
    scope = 'Equal contributions from measured colour (50%) and published shot scale/composition (50%). Human and model labels have equal weight. Missing framing evidence contributes no agreement; labels are never inferred here.'
    if left.status != 'ready' or right.status != 'ready':
        return {'pairs': [], 'scope': scope, 'notice': 'Both films need available frame analysis.'}
    data = [load_signature(settings.BASE_DIR.parent, a.movie.tmdb_id, a.source_sha256, a.quality.get('palette_method')) for a in (left, right)]
    sources = [{str(fid): vector for fid, vector in zip(d['frame_ids'], d['frames'])} if d is not None else {} for d in data]
    frames = [left.frames, right.frames]
    if any(not side or any(f.get('frame_id') not in source for f in side) for side, source in zip(frames, sources)):
        return {'pairs': [], 'scope': scope, 'notice': 'Frame matching is unavailable until colour-distribution caches are prepared for these images.'}
    vectors = [np.asarray([source[f['frame_id']] for f in side]) for side, source in zip(frames, sources)]
    scores = combined_scores(similarity_matrix(vectors[0], vectors[1]), *frames)
    pairs = []
    for i, j, score in top_pairs(scores):
        pairs.append({'left': {**left.frames[i], 'image_url': '/api/v1/cinematography/frames/' + left.frames[i]['image']},
                      'right': {**right.frames[j], 'image_url': '/api/v1/cinematography/frames/' + right.frames[j]['image']},
                      'similarity': round(score * 100, 1)})
    return {'pairs': pairs, 'scope': scope, 'notice': ''}
