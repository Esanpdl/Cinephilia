"""Restore the single-film BFI source after identifying a trilogy replacement."""
import hashlib
import json
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'data/raw/trailers'
status_path = base / '_download_status.json'
state = json.loads(status_path.read_text(encoding='utf-8'))
record = state['movies']['307']
if 'trilogy' in record.get('video_title', '').lower():
    original = Path(record['archived_original']).resolve()
    if not original.is_relative_to((base / '_superseded').resolve()) or not original.is_file():
        raise ValueError('Original archive path did not validate.')
    current = base / '307.mp4'
    digest = hashlib.sha256(current.read_bytes()).hexdigest()
    rejected = base / '_superseded' / f'307-rejected-trilogy-{digest[:12]}.mp4'
    if not rejected.exists():
        shutil.copy2(current, rejected)
    shutil.copy2(original, current)
    state['movies']['307'] = record['previous']
    state['movies']['307']['restoration_reason'] = 'Reject multi-film trilogy trailer; restore original single-film BFI reissue source.'
    status_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
review = ROOT / 'data/phase8/source_decisions.json'
decisions = json.loads(review.read_text(encoding='utf-8')) if review.exists() else {}
decisions['307'] = {'status': 'accepted', 'reason': 'Original BFI Rome, Open City single-film reissue trailer restored. Trilogy replacement rejected.'}
decisions['83761'] = {'status': 'rejected', 'reason': 'Music excerpt rather than a verified cinematic trailer; analysis withheld.'}
review.write_text(json.dumps(decisions, indent=2), encoding='utf-8')
print('Source review recorded; originals preserved.')
