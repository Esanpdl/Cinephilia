"""Apply source-specific review without changing the automatic extractor."""
from copy import deepcopy
import hashlib
import json

SOURCE_LABELS = {
    'trailer': 'Trailer',
    'promo': 'Single-film promotional video',
    'featurette': 'Promotional featurette',
    'excerpt': 'Scene excerpt',
    'compilation': 'Combined film clips',
    'shared_compilation': 'Shared War Trilogy footage',
}


def review_fingerprint(decision):
    recipe = {key: decision.get(key) for key in
              ['source_sha256', 'source_kind', 'source_note', 'excluded_frame_indices']}
    return hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()


def review_error(data, decision):
    """Return why accepted evidence cannot be published, or an empty string."""
    if decision.get('status') != 'accepted':
        return ''
    if not decision.get('source_sha256') or decision['source_sha256'] != data.get('source_sha256'):
        return 'Source review belongs to a different video; review the current source.'
    if data.get('source_review', {}).get('recipe_sha256') != review_fingerprint(decision):
        return 'Source review must be applied to the current analysis.'
    removed = set(decision.get('excluded_frame_indices', []))
    if any(frame['index'] in removed for key in ['all_frames', 'frames', 'study_cards'] for frame in data.get(key, [])):
        return 'Reviewed exclusions remain in the visual evidence.'
    return ''


def apply_review(data, decision, frame_root):
    if decision.get('status') != 'accepted':
        return data
    if decision.get('source_sha256') != data.get('source_sha256'):
        raise ValueError('Review checksum differs from the video; a new source review is required.')
    if decision.get('source_kind') not in SOURCE_LABELS:
        raise ValueError('An accepted source needs a recognized source kind.')
    fingerprint = review_fingerprint(decision)
    previous = data.get('source_review', {})
    if previous.get('recipe_sha256') == fingerprint:
        error = review_error(data, decision)
        if error:
            raise ValueError(error)
        return data
    if previous:
        raise ValueError('Review changed; rerun extraction with --force to recover original samples.')
    result = deepcopy(data)
    removed = set(decision.get('excluded_frame_indices', []))
    excluded = [f for f in result['all_frames'] if f['index'] in removed]
    if excluded:
        from extractor import refine_text_masks
        result['all_frames'] = [f for f in result['all_frames'] if f['index'] not in removed]
        result['excluded']['source_review'] = len(excluded)
        result = refine_text_masks(result, frame_root)
    result['source_review'] = {
        'recipe_sha256': fingerprint,
        'source_kind': decision['source_kind'],
        'source_note': decision.get('source_note', ''),
        'excluded_frame_indices': sorted(f['index'] for f in excluded),
        'method': decision.get('review_method', 'Recorded contact-sheet review; automatic extraction is unchanged.'),
    }
    return result
