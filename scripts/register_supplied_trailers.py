"""Record explicit owner approval for the installed local batch, without web lookup."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/phase8/2026-09-18-owner-supplied'


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def main():
    plan = json.loads((BASE / 'prepared.json').read_text(encoding='utf-8'))
    links_path = BASE / 'source-links.json'
    links = json.loads(links_path.read_text(encoding='utf-8')) if links_path.exists() else {}
    state_path = ROOT / 'data/raw/trailers/_download_status.json'
    decisions_path = ROOT / 'data/phase8/source_decisions.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    decisions = json.loads(decisions_path.read_text(encoding='utf-8'))
    rows = {str(r['tmdb_id']): r for r in json.loads((ROOT / 'data/phase8/trailer_manifest_500.json').read_text(encoding='utf-8'))['movies']}
    for mid, output in plan['outputs'].items():
        video = Path(output['target_path'])
        with video.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != output['sha256']:
                raise ValueError(f'Installed video does not match preparation: {mid}')
    for name, contents in [('previous-download-status.json', state), ('previous-source-decisions.json', decisions)]:
        backup = BASE / name
        if not backup.exists():
            write_json(backup, contents)
    now = datetime.now(timezone.utc).isoformat()
    for mid, output in plan['outputs'].items():
        video = Path(output['target_path'])
        shared = mid in ['307', '8016', '8429']
        kind = 'shared_compilation' if shared else 'compilation' if len(output['parts']) > 1 else 'promo' if mid == '897' else 'excerpt' if mid == '83761' else 'trailer'
        if shared:
            note = 'Includes shared footage from Rome, Open City, Paisan and Germany, Year Zero, used across all three films at the project owner\'s request. Measurements describe this supplied source, not footage attributed exclusively to this film.'
        elif mid in ['34181', '1405']:
            note = f"The project owner's {len(output['parts'])} supplied clips combined into one study video. Timestamps refer to this combined video."
        elif mid == '897':
            note = 'The Visuals of Satyajit Ray\'s Aparajito, accepted as the study source at the project owner\'s request.'
        else:
            note = 'Local video supplied and accepted by the project owner; measurements describe this supplied edition.'
        offsets = [0.0]
        if len(output['parts']) > 1:
            # Read actual concat timestamp offsets without decoding/transcoding again.
            probe = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-loglevel', 'debug',
                '-f', 'concat', '-safe', '0', '-i', str(BASE / f'{mid}.concat.txt'),
                '-map', '0:v:0', '-c', 'copy', '-f', 'null', '-'], capture_output=True, text=True, errors='replace', check=True)
            starts = {}
            for line in probe.stderr.splitlines():
                match = re.search(r'file:(\d+) stream:0 pts:\S+ pts_time:(\S+).*-> pts:\S+ pts_time:(\S+)', line)
                if match:
                    index, before, after = match.groups()
                    starts.setdefault(int(index), round(float(after) - float(before), 6))
            if len(starts) != len(output['parts']):
                raise ValueError(f'Could not identify each concat boundary for {mid}')
            offsets = [starts[i] for i in range(len(output['parts']))]
        components = []
        for index, key in enumerate(output['parts']):
            part = plan['parts'][key]
            components.append({'key': key, 'original_filename': part['original_filename'],
                               'path': Path(part['archive_path']).relative_to(ROOT).as_posix(),
                               'sha256': part['sha256'], 'original_duration': part['seconds'],
                               'start': offsets[index], 'source_url': links.get(key, '')})
        title = (rows[mid]['title'] + ' - supplied film clips and War Trilogy trailer') if shared and len(components) > 1 else (
            'Roberto Rossellini: The War Trilogy' if shared else rows[mid]['title'] + f' - {len(components)} combined clips' if len(components) > 1 else Path(components[0]['original_filename']).stem)
        previous = state['movies'].get(mid, {})
        state['movies'][mid] = {
            'tmdb_id': int(mid), 'title': rows[mid]['title'], 'status': 'existing',
            'source_url': links.get(output['parts'][0], '') if len(components) == 1 else '',
            'video_id': '', 'video_title': title, 'source_kind': kind,
            'provided_by': 'project_owner', 'approval_basis': 'Explicit instruction to use these downloaded videos without further source search.',
            'checked_at': now, 'sha256': output['sha256'], 'bytes': video.stat().st_size,
            'duration_seconds': output['seconds'], 'components': components,
            'batch': plan['batch'], 'prior_metadata_receipt': (BASE / 'previous-download-status.json').relative_to(ROOT).as_posix(),
        }
        decisions[mid] = {
            'status': 'accepted', 'reason': 'Explicitly accepted by the project owner. ' + note,
            'source_sha256': output['sha256'], 'source_url': state['movies'][mid]['source_url'], 'source_kind': kind,
            'source_note': note, 'excluded_frame_indices': [], 'reviewed_at': now,
            'review_method': 'Explicit project-owner source approval; automatic frame and text filtering retained. No further source search.',
            'review_evidence': (BASE / 'prepared.json').relative_to(ROOT).as_posix(),
            'shared_movie_ids': [307, 8429, 8016] if shared else [],
        }
    write_json(state_path, state)
    write_json(decisions_path, decisions)
    print(f'Registered {len(plan["outputs"])} owner-approved sources; {len(links)}/{len(plan["parts"])} YouTube component links supplied. No local playback.')


if __name__ == '__main__':
    main()
