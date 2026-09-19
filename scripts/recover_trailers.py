"""Try recorded alternative trailers; preserve replaced originals and provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data/raw/technique_sources/webScraping'))
from download_trailers import atomic_json, ffmpeg_path, now, safe_message, verify_video, Logger
import cv2
import numpy as np
import yt_dlp


def has_color(path):
    cap = cv2.VideoCapture(str(path))
    count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    colored = 0
    try:
        for fraction in np.linspace(.15, .85, 12):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(count * fraction))
            ok, frame = cap.read()
            if ok:
                chroma = np.ptp(frame.astype(np.int16), axis=2)
                colored += float((chroma > 15).mean()) > .2
    finally:
        cap.release()
    return colored >= 4


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tmdb-id', type=int, action='append')
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    destination = ROOT / 'data/raw/trailers'
    state_path = destination / '_download_status.json'
    audit = json.loads((ROOT / 'data/phase8/source_audit.json').read_text(encoding='utf-8'))['movies']
    recovery_path = ROOT / 'data/phase8/recovery.json'
    recovery = json.loads(recovery_path.read_text(encoding='utf-8')) if recovery_path.exists() else {}
    ffmpeg = ffmpeg_path()
    runtime = 'deno' if shutil.which('deno') else 'node'
    # Share the original downloader's OS lock; never race its file/status writes.
    lock = (destination / '_download.lock').open('a+b')
    lock.seek(0)
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        for row in sorted(audit, key=lambda r: r['tmdb_id'] != 496243):
            mid = row['tmdb_id']
            if args.tmdb_id and mid not in args.tmdb_id:
                continue
            if not row['flags'] or recovery.get(str(mid), {}).get('status') == 'recovered':
                continue
            candidates_path = ROOT / f'data/phase8/candidates/{mid}.json'
            if not candidates_path.exists():
                continue
            candidates = json.loads(candidates_path.read_text(encoding='utf-8'))
            extra = ROOT / f'data/phase8/candidates/{mid}-external.json'
            if extra.exists():
                candidates = json.loads(extra.read_text(encoding='utf-8')) + candidates
            state = json.loads(state_path.read_text(encoding='utf-8'))
            old = state['movies'].get(str(mid), {})
            tried = recovery.get(str(mid), {}).get('attempts', [])
            record = {'status': 'unresolved', 'title': row['title'], 'attempts': tried}
            attempts = 0
            for candidate in candidates:
                key = candidate['key']
                if key == old.get('video_id') or any(a['key'] == key and 'WinError 5' not in a.get('error', '') for a in tried):
                    continue
                if re.search(r'black.{0,5}white|b&w|colori[sz]ed|three reasons|\bclips?\b|excerpt|sizzle|teaser|scene|tribute|fan.made|trilogy|\d+ films', candidate['name'], re.I):
                    continue
                if attempts >= args.attempts:
                    break
                attempts += 1
                url = f'https://www.youtube.com/watch?v={key}' if candidate['site'] == 'YouTube' else f'https://vimeo.com/{key}'
                stage = destination / '_replacements' / str(mid) / key
                stage.mkdir(parents=True, exist_ok=True)
                logger = Logger()
                print(f"{mid} {row['title']}: {candidate['name']} ({key})", flush=True)
                try:
                    options = {
                        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]',
                        'format_sort': ['vcodec:h264'], 'merge_output_format': 'mp4',
                        'postprocessors': [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'}],
                        'outtmpl': str(stage / 'video.%(ext)s'), 'ffmpeg_location': ffmpeg,
                        'js_runtimes': {runtime: {}}, 'noplaylist': True, 'quiet': True,
                        'logger': logger, 'socket_timeout': 20, 'retries': 1, 'fragment_retries': 1,
                    }
                    with yt_dlp.YoutubeDL(options) as downloader:
                        info = downloader.extract_info(url, download=False)
                        if not info or info.get('id') != key or not 30 <= (info.get('duration') or 0) <= 360:
                            raise ValueError('Candidate identity/duration is unsuitable for a trailer.')
                        if re.search(r'fan.made|recap|explained|three reasons|\bclips?\b|excerpts|sizzle|premiere|video essay|trilogy|\d+ films', info.get('title', ''), re.I):
                            raise ValueError('Upload title identifies non-trailer material.')
                        downloader.process_info(info)
                    video = stage / 'video.mp4'
                    verify_video(video, ffmpeg)
                    if mid == 496243 and not has_color(video):
                        raise ValueError('Parasite replacement did not pass the color check.')
                    final = destination / f'{mid}.mp4'
                    archived = None
                    if final.exists():
                        checksum = hashlib.sha256(final.read_bytes()).hexdigest()
                        archive = destination / '_superseded'
                        archive.mkdir(exist_ok=True)
                        archived = archive / f'{mid}-{checksum[:12]}.mp4'
                        if not archived.exists():
                            shutil.copy2(final, archived)
                    video.replace(final)
                    new = {'tmdb_id': mid, 'title': row['title'], 'source_url': url, 'checked_at': now(), 'status': 'downloaded',
                           'bytes': final.stat().st_size, 'video_id': key, 'video_title': info['title'],
                           'uploader': info.get('uploader'), 'duration_seconds': info.get('duration'),
                           'width': info.get('width'), 'height': info.get('height'), 'replacement': True,
                           'source_evidence': candidate, 'previous': old,
                           'archived_original': str(archived) if archived else None}
                    state['movies'][str(mid)] = new
                    state['updated_at'] = now()
                    atomic_json(state_path, state)
                    tried.append({'key': key, 'status': 'downloaded'})
                    record.update(status='recovered', source_url=url)
                    print('  Recovered and verified.', flush=True)
                    break
                except Exception as error:
                    tried.append({'key': key, 'status': 'failed', 'error': safe_message(error)})
                    print('  ' + safe_message(error), flush=True)
                finally:
                    (stage / 'download.log').write_text('\n'.join(logger.messages), encoding='utf-8')
            recovery[str(mid)] = record
            atomic_json(recovery_path, recovery)
    finally:
        lock.close()


if __name__ == '__main__':
    main()
