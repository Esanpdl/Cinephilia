"""Preserve a runnable, checksum-verified copy of the local palette extractor."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'training/visual'
SOURCES = {
    'extractor.py': 'backend/apps/cinematography/services/visual_analysis.py',
    'source_review.py': 'backend/apps/cinematography/services/source_review.py',
    'analyze_trailers.py': 'scripts/analyze_trailers.py',
    'requirements.txt': 'training/visual-requirements.txt',
    'source-reviews.json': 'data/phase8/source_decisions.json',
    'supplied-source-links.json': 'data/phase8/2026-09-18-owner-supplied/source-links.json',
}


def preserved_bytes(name, source):
    data = source.read_bytes()
    if name == 'source_review.py':
        return data.replace(b'from .visual_analysis import', b'from extractor import')
    if name != 'analyze_trailers.py':
        return data
    # Make the preserved runner load the preserved algorithm, not the backend.
    text = data.decode('utf-8').replace('parents[1]', 'parents[2]')
    old = "sys.path.insert(0, str(ROOT / 'backend'))\nfrom apps.cinematography.services.visual_analysis import analyze, refine_text_masks, VERSION"
    text = text.replace('\r\n', '\n')
    if old not in text:
        raise ValueError('Runner imports changed; update the snapshot adapter.')
    text = text.replace(old, 'from extractor import analyze, refine_text_masks, VERSION')
    text = text.replace('from apps.cinematography.services.source_review import', 'from source_review import')
    return text.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify without changing files.')
    args = parser.parse_args()
    receipt = {'method': 'Local OpenCV extraction with pretrained OCR; no new model training.', 'files': {}}
    if not args.check:
        TARGET.mkdir(parents=True, exist_ok=True)
    for name, relative in SOURCES.items():
        source = ROOT / relative
        expected = preserved_bytes(name, source)
        destination = TARGET / name
        if args.check:
            if not destination.exists() or destination.read_bytes() != expected:
                raise SystemExit(f'Preserved source differs: {destination}')
        else:
            destination.write_bytes(expected)
        receipt['files'][name] = {
            'source': relative,
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'preserved_sha256': hashlib.sha256(expected).hexdigest(),
        }
    manifest = TARGET / 'source-manifest.json'
    if args.check:
        if not manifest.exists() or json.loads(manifest.read_text(encoding='utf-8')) != receipt:
            raise SystemExit('Preserved source manifest differs.')
    else:
        manifest.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(('Verified' if args.check else 'Preserved') + ' runnable palette extraction sources in training/visual.')


if __name__ == '__main__':
    main()
