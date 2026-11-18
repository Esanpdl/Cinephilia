"""Optional frozen semantic vectors for search discovery; NumPy-only serving."""
from functools import lru_cache
import hashlib
import json
import logging
from pathlib import Path
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class SemanticDiscovery:
    def __init__(self, base, directory, manifest):
        self.base, self.manifest = base, manifest
        if base.manifest['catalog_sha256'] != manifest['catalog_sha256']:
            raise ValueError('Semantic catalogue is stale')
        path = Path(directory) / 'vectors.npz'
        if checksum(path) != manifest['vectors_sha256']:
            raise ValueError('Semantic vectors changed')
        with np.load(path, allow_pickle=False) as data:
            ids, self.vectors = data['movie_ids'], data['vectors'].astype(np.float32)
        if not np.array_equal(ids, base.movie_ids) or self.vectors.shape[0] != len(ids):
            raise ValueError('Semantic IDs differ from content catalogue')
        if not np.isfinite(self.vectors).all() or not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=.002):
            raise ValueError('Invalid semantic vectors')
        self.vectors.setflags(write=False)
        self.rows = {int(mid): i for i, mid in enumerate(ids)}
        self.model_name = manifest['model_name']

    def contains(self, mid):
        return self.base.contains(mid)

    def movie(self, mid):
        return self.base.movie(mid)

    def score_discovery(self, seed, candidate_ids, weights):
        candidates = list(candidate_ids)
        lexical = self.base.score_discovery(seed, candidates, weights)
        known = [mid for mid in candidates if mid in self.rows]
        if not known or seed not in self.rows:
            return lexical
        # Fixed evaluated blend; mode identity/genre controls stay explicit.
        semantic = np.clip(self.vectors[[self.rows[mid] for mid in known]] @ self.vectors[self.rows[seed]], 0, 1)
        weight = self.manifest['semantic_weight']
        return {**lexical, **{mid: float(weight*value + (1-weight)*lexical[mid]) for mid, value in zip(known, semantic)}}

    def explain_discovery(self, seed, target, weights):
        result = self.base.explain_discovery(seed, target, weights)
        similarity = float(np.clip(self.vectors[self.rows[seed]] @ self.vectors[self.rows[target]], 0, 1))
        result['contributions'] = {k: v*(1-self.manifest['semantic_weight']) for k, v in result['contributions'].items()}
        result['contributions']['semantic'] = self.manifest['semantic_weight']*similarity
        return result


@lru_cache(maxsize=2)
def _load(base, directory, fingerprint):
    manifest_path = Path(directory) / 'manifest.json'
    if checksum(manifest_path) != fingerprint:
        raise ValueError('Semantic manifest changed')
    return SemanticDiscovery(base, directory, json.loads(manifest_path.read_text('utf-8')))


def get_discovery_service(base):
    if base is None:
        return None
    root = settings.BASE_DIR.parent / 'data/discovery'
    pointer_path = root / 'current.json'
    if not pointer_path.exists():
        return base
    try:
        pointer = json.loads(pointer_path.read_text('utf-8'))
        directory = (root / pointer['directory']).resolve()
        if not directory.is_relative_to((root/'artifacts').resolve()):
            raise ValueError('Semantic artifact path escapes its directory')
        return _load(base, str(directory), pointer['manifest_sha256'])
    except (OSError, ValueError, KeyError) as error:
        logger.warning('Semantic discovery unavailable; using structured content: %s', error)
        return base
