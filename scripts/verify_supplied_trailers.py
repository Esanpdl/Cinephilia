"""Verify local supplied-file preservation, composite decoding and frame provenance."""
import hashlib
import json
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/phase8/2026-09-18-owner-supplied'


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    plan = json.loads((BASE / 'prepared.json').read_text(encoding='utf-8'))
    links = json.loads((BASE / 'source-links.json').read_text(encoding='utf-8'))
    report = {'originals': 0, 'sources': [], 'errors': []}
    for key, part in plan['parts'].items():
        archived = Path(part['archive_path'])
        if not archived.is_file() or sha256(archived) != part['sha256']:
            report['errors'].append(f'{key}: supplied original missing or changed')
        else:
            report['originals'] += 1
        if Path(part['original_path']).exists():
            report['errors'].append(f'{key}: download was not moved')
    for mid, source in plan['outputs'].items():
        path = Path(source['target_path'])
        if sha256(path) != source['sha256']:
            report['errors'].append(f'{mid}: installed video differs')
        cap = cv2.VideoCapture(str(path))
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = count / fps
        offset, checked = 0, []
        try:
            for key in source['parts']:
                seconds = plan['parts'][key]['seconds']
                for timestamp in [offset + .5, min(offset + seconds - .5, duration - .5)]:
                    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                    if not cap.read()[0]:
                        report['errors'].append(f'{mid}: cannot decode at {timestamp:.3f}s')
                    checked.append(round(timestamp, 3))
                offset += seconds
        finally:
            cap.release()
        analysis = json.loads((ROOT / f'data/phase8/analysis/{mid}.json').read_text(encoding='utf-8'))
        if analysis['source_sha256'] != source['sha256']:
            report['errors'].append(f'{mid}: analysis still belongs to an older video')
        if len(analysis.get('source_components', [])) != len(source['parts']):
            report['errors'].append(f'{mid}: component provenance missing')
        if 'project-owner' not in analysis.get('source_review', {}).get('method', ''):
            report['errors'].append(f'{mid}: owner acceptance missing')
        expected_url = links.get(source['parts'][0], '') if len(source['parts']) == 1 else ''
        if analysis.get('source_url') != expected_url:
            report['errors'].append(f'{mid}: playback URL does not match the supplied link')
        for part in analysis.get('source_components', []):
            if part.get('source_url', '') != links.get(part['key'], ''):
                report['errors'].append(f'{mid}: incorrect component URL for {part["key"]}')
        report['sources'].append({'tmdb_id': int(mid), 'duration': round(duration, 3),
                                  'components': len(source['parts']), 'checked_timestamps': checked,
                                  'retained_frames': analysis['retained_count']})
    report['passed'] = not report['errors']
    (BASE / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(not report['passed'])


if __name__ == '__main__':
    main()
