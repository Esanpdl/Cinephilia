"""Prepare the owner's September 18 local videos, without searching or downloading."""
import hashlib
import json
from pathlib import Path
import subprocess
import cv2
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
BATCH = '2026-09-18-owner-supplied'
BASE = ROOT / 'data/phase8' / BATCH
RAW = ROOT / 'data/raw/trailers'


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inspect(path):
    cap = cv2.VideoCapture(str(path))
    try:
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        ok, frame = cap.read()
        if not ok or fps <= 0 or count <= 0:
            raise ValueError(f'Cannot decode {path.name}')
        return {'seconds': round(count / fps, 6), 'fps': fps,
                'width': frame.shape[1], 'height': frame.shape[0]}
    finally:
        cap.release()


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    existing = BASE / 'prepared.json'
    if existing.exists():
        print(f'Preparation already recorded: {existing}. Use the saved plan to resume.')
        return
    files = sorted(ROOT.glob('*.mp4'), key=lambda p: p.name.casefold())

    def one(prefix):
        matches = [p for p in files if p.name.casefold().startswith(prefix.casefold())]
        if len(matches) != 1:
            raise ValueError(f'Expected one supplied file beginning {prefix!r}, found {len(matches)}')
        return matches[0]

    sources = {
        '5801': one('Pather Panchali'), '896': one('Apur Sansar'),
        '897': one('The Visuals of Satyajit'), '701': one('Our Hospitality'),
        '25768': one('Steamboat Bill'), '31527': one('The Scarlet Empress'),
        '697': one('Trailer October'), '83761': one('Life, and Nothing'),
        'war-trilogy': one('Roberto Rossellini'),
        '8016-film': one('GERMANIA ANNO ZERO'), '8429-film': one('#Neorrealismo'),
        '34181-part-01': one('Gertrud (1964) greek'),
        '34181-part-02': one('Gertrud (1964), long'),
        '34181-part-03': one('Gertrud (Carl'),
        '34181-part-04': one('Gertrud by the Lake'),
        '1405-part-01': one('Greed (1924) -'),
        '1405-part-02': one('GREED (1924) Directed'),
    }
    mapping = {mid: [mid] for mid in ['5801','896','897','701','25768','31527','697','83761']}
    mapping.update({'34181': [f'34181-part-0{i}' for i in range(1,5)],
                    '1405': ['1405-part-01','1405-part-02'],
                    '307': ['war-trilogy'], '8016': ['8016-film','war-trilogy'],
                    '8429': ['8429-film','war-trilogy']})
    parts = {}
    for key, source in sources.items():
        parts[key] = {'original_path': str(source.resolve()), 'original_filename': source.name,
                      'archive_path': str((RAW / 'supplied' / BATCH / f'{key}.mp4').resolve()),
                      'sha256': digest(source), 'bytes': source.stat().st_size, **inspect(source)}
    (BASE / 'inputs.json').write_text(json.dumps(parts, ensure_ascii=False, indent=2), encoding='utf-8')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    normalized = BASE / 'normalized'
    normalized.mkdir(exist_ok=True)
    composite_keys = {key for keys in mapping.values() if len(keys) > 1 for key in keys}
    for key in sorted(composite_keys):
        source = sources[key]
        output = normalized / f'{key}.mp4'
        print(f'Normalizing {key} ({parts[key]["seconds"]:.1f}s)', flush=True)
        # Preserve aspect ratio and audio. No tinting, denoising or grading.
        with (BASE / f'{key}.ffmpeg.log').open('w', encoding='utf-8') as log:
            subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-y', '-i', str(source),
                '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                '-map', '0:v:0', '-map', '0:a:0?', '-map', '1:a:0',
                '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-threads', '2', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '160k',
                '-t', str(parts[key]['seconds']), '-movflags', '+faststart', str(output)],
                stdout=log, stderr=subprocess.STDOUT, check=True)
    outputs = {}
    for mid, keys in mapping.items():
        if len(keys) == 1:
            prepared_path = None
            details = parts[keys[0]]
            checksum = details['sha256']
            duration = details['seconds']
        else:
            # Normalization gives all clips identical video/audio parameters.
            concat = BASE / f'{mid}.concat.txt'
            concat.write_text(''.join(f"file '{(normalized / (key + '.mp4')).as_posix()}'\n" for key in keys), encoding='utf-8')
            prepared_path = BASE / f'{mid}.mp4'
            print(f'Combining {len(keys)} clips for {mid}', flush=True)
            with (BASE / f'{mid}.concat.log').open('w', encoding='utf-8') as log:
                subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-y', '-f', 'concat', '-safe', '0',
                    '-i', str(concat), '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy',
                    '-movflags', '+faststart', str(prepared_path)], stdout=log, stderr=subprocess.STDOUT, check=True)
            checksum, duration = digest(prepared_path), inspect(prepared_path)['seconds']
            expected = sum(parts[key]['seconds'] for key in keys)
            if abs(duration - expected) > 1:
                raise ValueError(f'Combined duration differs for {mid}: {duration} vs {expected}')
        outputs[mid] = {'parts': keys, 'prepared_path': str(prepared_path.resolve()) if prepared_path else None,
                        'target_path': str((RAW / f'{mid}.mp4').resolve()),
                        'previous_path': str((RAW / 'previous' / BATCH / f'{mid}.mp4').resolve()),
                        'sha256': checksum, 'seconds': duration}
    plan = {'batch': BATCH, 'parts': parts, 'outputs': outputs,
            'assembly': '1280x720 aspect-preserving padding, 25fps, H.264 CRF18, AAC audio; sequential concatenation.'}
    existing.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Prepared {len(outputs)} movie sources from {len(parts)} supplied files: {existing}', flush=True)


if __name__ == '__main__':
    main()
