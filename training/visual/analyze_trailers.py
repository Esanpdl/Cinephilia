"""Resume local sampled-frame extraction for the 500-film manifest."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
from extractor import analyze, refine_text_masks, VERSION
from source_review import apply_review, review_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tmdb-id', type=int, action='append')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    rows = json.loads((ROOT / 'data/phase8/trailer_manifest_500.json').read_text(encoding='utf-8'))['movies']
    state = json.loads((ROOT / 'data/raw/trailers/_download_status.json').read_text(encoding='utf-8'))['movies']
    decisions_path = ROOT / 'data/phase8/source_decisions.json'
    decisions = json.loads(decisions_path.read_text(encoding='utf-8')) if decisions_path.exists() else {}
    output = ROOT / 'data/phase8/analysis'
    output.mkdir(exist_ok=True)

    def run(row):
        mid = row['tmdb_id']
        video = ROOT / f'data/raw/trailers/{mid}.mp4'
        result_path = output / f'{mid}.json'
        if not video.exists():
            return mid, 'missing'
        signature = [video.stat().st_size, video.stat().st_mtime_ns, VERSION]
        old = None
        if result_path.exists() and not args.force:
            old = json.loads(result_path.read_text(encoding='utf-8'))
            metadata = state.get(str(mid), {})
            same_metadata = (old.get('source_components', []) == metadata.get('components', []) and
                             old.get('source_url') == metadata.get('source_url', row['trailer_url']))
            if old.get('file_signature') == signature and not review_error(old, decisions.get(str(mid), {})) and same_metadata:
                return mid, 'cached'
        try:
            if old and old.get('file_signature') == signature:
                result = old
            elif old and old.get('file_signature', [])[:2] == signature[:2]:
                result = refine_text_masks(old, ROOT / 'data/phase8/frames')
            else:
                result = analyze(video, row, state.get(str(mid), {}), ROOT / 'data/phase8/frames')
            decision = decisions.get(str(mid), {})
            if decision.get('status') == 'accepted' and not result.get('source_review'):
                archive = output / 'before-source-review'
                archive.mkdir(exist_ok=True)
                backup = archive / f"{mid}-{result['source_sha256'][:12]}-{VERSION}.json"
                if not backup.exists():
                    backup.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            result = apply_review(result, decision, ROOT / 'data/phase8/frames')
            result['source_url'] = state.get(str(mid), {}).get('source_url', row['trailer_url'])
            if state.get(str(mid), {}).get('components'):
                result['source_components'] = state[str(mid)]['components']
            result['file_signature'] = signature
            temporary = result_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(result_path)
            return mid, f"{result['color_mode']} ({result['retained_count']} frames)"
        except Exception as error:
            return mid, 'failed: ' + str(error)

    started = time.monotonic()
    selected = [row for row in rows if not args.tmdb_id or row['tmdb_id'] in args.tmdb_id]
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(run, row) for row in selected]
        for job in as_completed(jobs):
            mid, status = job.result()
            results[str(mid)] = status
            print(f'{len(results)}/{len(selected)} {mid}: {status}', flush=True)
    report = {'seconds': round(time.monotonic() - started, 2), 'results': results}
    (output / 'run.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
