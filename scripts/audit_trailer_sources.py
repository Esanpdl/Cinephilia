"""Inventory trailer provenance and discover alternative TMDB video candidates."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.movies.services.tmdb import TMDBClient, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discover', action='store_true')
    args = parser.parse_args()
    rows = json.loads((ROOT / 'data/phase8/trailer_manifest_500.json').read_text(encoding='utf-8'))['movies']
    state = json.loads((ROOT / 'data/raw/trailers/_download_status.json').read_text(encoding='utf-8'))['movies']
    report = []
    client = TMDBClient() if args.discover else None
    try:
        for movie in rows:
            mid = movie['tmdb_id']
            record = state.get(str(mid), {})
            title = record.get('video_title', '')
            flags = []
            if not (ROOT / f'data/raw/trailers/{mid}.mp4').exists():
                flags.append('missing')
            extra_title = re.sub(re.escape(movie['title']), '', title, flags=re.I)
            if re.search(r'fan[ -]?made|fan trailer|tribute|recap|explained|video essay|\bclips?\b|\bscene\b|full movie|interview|making.of|behind.the.scenes|opening|credits|music video|three reasons|excerpts|premiere|insanity|dance of|trilogy|vivaldi|\d+ films', extra_title, re.I):
                flags.append('possibly_not_trailer')
            if title and not re.search(r'trailer|tráiler|bande.annonce|teaser|予告|трейлер', title, re.I):
                flags.append('title_needs_review')
            if re.search(r'black.{0,5}white|b\s*&\s*w|colori[sz]ed|colourised', title, re.I):
                flags.append('edition_review')
            if mid == 496243:
                flags.append('user_requested_color_replacement')
            if record.get('duration_seconds', 120) > 360 or record.get('duration_seconds', 120) < 30:
                flags.append('unusual_duration')
            item = {**movie, 'download': record, 'flags': flags}
            if flags:
                print(json.dumps({'id': mid, 'film': movie['title'], 'video': title, 'flags': flags}), flush=True)
            if client and flags:
                destination = ROOT / f'data/phase8/candidates/{mid}.json'
                if destination.exists():
                    item['candidates'] = json.loads(destination.read_text(encoding='utf-8'))
                else:
                    videos = client.get(f'/movie/{mid}/videos', {'language': 'en-US'})['results']
                    candidates = [v for v in videos if v.get('site') in {'YouTube', 'Vimeo'} and v.get('type') == 'Trailer']
                    candidates.sort(key=lambda v: (not v.get('official', False), bool(re.search(r'black.{0,5}white|b&w|colori[sz]ed', v['name'], re.I))))
                    write_json(destination, candidates)
                    item['candidates'] = candidates
            report.append(item)
    finally:
        if client:
            client.close()
    output = {'counts': dict(Counter(flag for row in report for flag in row['flags'])), 'movies': report}
    write_json(ROOT / 'data/phase8/source_audit.json', output)
    print(output['counts'])


if __name__ == '__main__':
    main()
