"""Check the complete extraction inventory and, optionally, its database import."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from apps.cinematography.services.visual_analysis import VERSION
from apps.cinematography.services.source_review import review_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'data/phase8'
    rows = json.loads((base / 'trailer_manifest_500.json').read_text(encoding='utf-8'))['movies']
    run = json.loads((base / 'analysis/run.json').read_text(encoding='utf-8'))
    decisions = json.loads((base / 'source_decisions.json').read_text(encoding='utf-8'))
    ids = {r['tmdb_id'] for r in rows}
    errors, unavailable, records = [], [], {}

    def check(condition, message):
        if not condition:
            errors.append(message)

    check(len(rows) == len(ids) == 500, 'Selection must retain exactly 500 unique films.')
    check({r['selection_rank'] for r in rows} == set(range(1, 501)), 'Selection ranks are incomplete.')
    check(set(run['results']) == {str(mid) for mid in ids}, 'The extraction run did not finish the full selection.')
    frames_checked = 0
    for row in rows:
        mid = row['tmdb_id']
        video = ROOT / f'data/raw/trailers/{mid}.mp4'
        path = base / f'analysis/{mid}.json'
        if not video.exists():
            unavailable.append({'tmdb_id': mid, 'title': row['title'], 'reason': 'missing'})
            check(run['results'].get(str(mid)) == 'missing', f'{mid}: missing video not recorded in run.')
            continue
        if not path.exists():
            reason = run['results'].get(str(mid), '')
            unavailable.append({'tmdb_id': mid, 'title': row['title'], 'reason': reason})
            check(reason.startswith('failed:'), f'{mid}: analysis missing without a recorded extraction failure.')
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        records[mid] = data
        error = review_error(data, decisions.get(str(mid), {}))
        check(not error, f'{mid}: {error}')
        check(data.get('tmdb_id') == mid, f'{mid}: wrong analysis identity.')
        check(data.get('version') == VERSION, f'{mid}: outdated extraction version.')
        check(data.get('file_signature') == [video.stat().st_size, video.stat().st_mtime_ns, VERSION], f'{mid}: stale trailer analysis.')
        check(bool(data.get('text_masking')), f'{mid}: missing text exclusion evidence.')
        kept = data['all_frames']
        check(len(kept) == data['retained_count'] and len(kept) >= 5, f'{mid}: insufficient or inconsistent frame count.')
        check(len(kept) + sum(data['excluded'].values()) == data['sample_count'], f'{mid}: frame accounting does not add up.')
        vector = data['vector']
        check(len(vector) == 192 and all(math.isfinite(v) and v >= 0 for v in vector) and abs(sum(vector) - 1) < .00002, f'{mid}: invalid color histogram.')
        check(len(data['palette']) == 6 and abs(sum(p['weight'] for p in data['palette']) - 1) < .001, f'{mid}: invalid palette weights.')
        check(all(math.isfinite(v) and 0 <= v <= 1 for v in data['metrics'].values()), f'{mid}: invalid measurements.')
        images = {f['image'] for f in kept}
        check(len(images) == len(kept), f'{mid}: duplicate frame identities.')
        for frame in kept:
            image = (base / 'frames' / frame['image']).resolve()
            expected = (base / 'frames' / str(mid) / data['source_sha256'][:12]).resolve()
            check(image.parent == expected and image.is_file(), f'{mid}: missing or misattributed frame {frame["image"]}.')
            check(0 <= frame['timestamp'] <= data['duration'], f'{mid}: timestamp outside source duration.')
            check(0 <= frame['text_excluded_fraction'] <= 1, f'{mid}: invalid text mask fraction.')
            frames_checked += 1
        check(all(f['image'] in images for f in data['frames'] + data['study_cards']), f'{mid}: displayed evidence is not in the retained samples.')

    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'version': VERSION,
              'selected': len(rows), 'analyses': len(records), 'frames_checked': frames_checked,
              'color_counts': dict(Counter(d['color_mode'] for d in records.values())),
              'unavailable': unavailable}
    if args.database:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from django.db import connection
        from apps.cinematography.models import TrailerAnalysis, StudyCard
        analyses = list(TrailerAnalysis.objects.select_related('movie'))
        check({a.movie.tmdb_id for a in analyses} == ids and len(analyses) == 500, 'Database selection differs from the original 500.')
        ranks = {r['tmdb_id']: r['selection_rank'] for r in rows}
        by_pk = {a.pk: a for a in analyses}
        for obj in analyses:
            mid = obj.movie.tmdb_id
            check(obj.selection_rank == ranks.get(mid), f'{mid}: database selection rank changed.')
            check(obj.movie.is_technique_source, f'{mid}: selected film lacks scraped-source provenance.')
            if obj.status != 'ready':
                continue
            data = records.get(mid)
            check(data is not None, f'{mid}: published without local evidence.')
            if data:
                for field in ['version', 'source_sha256', 'source_url', 'source_title', 'color_mode', 'metrics', 'palette', 'vector', 'frames']:
                    check(getattr(obj, field) == data[field], f'{mid}: imported {field} differs from local evidence.')
        published_cards = 0
        for card in StudyCard.objects.filter(approved=True, analysis__status='ready'):
            mid = by_pk[card.analysis_id].movie.tmdb_id
            data = records.get(mid, {})
            check(card.image in {f['image'] for f in data.get('all_frames', [])}, f'{mid}: published card points to unretained evidence.')
            published_cards += 1
        report.update(status_counts=dict(Counter(a.status for a in analyses)),
                      published_color_counts=dict(Counter(a.color_mode for a in analyses if a.status == 'ready')),
                      published_cards=published_cards,
                      source_review_needed=[{'tmdb_id': a.movie.tmdb_id, 'title': a.movie.title, 'source_url': a.source_url,
                                             'source_title': a.source_title, 'reason': a.reason}
                                            for a in analyses if a.status == 'review'])
        connection.close()
    report.update(passed=not errors, errors=errors)
    (base / 'inventory-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.database:
        lines = ['# Trailer sources needing attention', '',
                 'These films retain their places in the selected 500. Their visual evidence is withheld.', '',
                 'Supply traceable single-film trailers or scene excerpts as `data/raw/trailers/<tmdb_id>.mp4`, record the source URL',
                 'in `_download_status.json`, then run the analysis, source audit, import and verification commands',
                 'in `docs/film-student-guide.md`. A replacement also needs a fresh source decision bound to its checksum.',
                 'No replacement downloads are performed by verification.', '',
                 '| TMDB ID | Film | Current source | Reason |', '| --- | --- | --- | --- |']
        for entry in unavailable + report.get('source_review_needed', []):
            source = entry.get('source_url', '')
            cells = [str(entry['tmdb_id']), entry['title'], source, entry['reason']]
            lines.append('| ' + ' | '.join(c.replace('|', '\\|').replace('\n', ' ') for c in cells) + ' |')
        (base / 'source-review-needed.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ['source_review_needed', 'unavailable']}, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
