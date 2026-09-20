"""Read titles for the owner's multi-clip links; never search or download videos."""
from concurrent.futures import ThreadPoolExecutor
import json
import html
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
IDS = ['i2S8HDggEO8', 'vTpSNLXSz6Q', 'agWx60csoyY', 'Q3US46U6-fc', '_H3AZUOm3U4', '_K6YXA8jY9E']


def fetch(key):
    url = 'https://www.youtube.com/watch?v=' + key
    try:
        endpoint = 'https://www.youtube.com/oembed?' + urlencode({'url': url, 'format': 'json'})
        with urlopen(Request(endpoint, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
            data = json.load(response)
        return {'id': key, 'source_url': url, 'title': data['title'], 'author': data.get('author_name', '')}
    except Exception as error:
        result = {'id': key, 'source_url': url, 'embed_metadata_error': str(error)}
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                page = response.read().decode('utf-8', errors='replace')
            title = re.search(r'<title>(.*?)</title>', page, re.S)
            if title:
                result['title'] = html.unescape(title.group(1)).removesuffix(' - YouTube')
            marker = 'ytInitialPlayerResponse = '
            if marker in page:
                player, _ = json.JSONDecoder().raw_decode(page.split(marker, 1)[1])
                status = player.get('playabilityStatus', {})
                result['watch_status'] = status.get('status')
                result['watch_reason'] = status.get('reason')
                result['playable_in_embed'] = status.get('playableInEmbed')
            if not result.get('title') or result['title'] == 'YouTube':
                result['error'] = 'Watch page did not expose the video title.'
        except Exception as watch_error:
            result['error'] = str(watch_error)
        return result


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, IDS))
    path = ROOT / 'data/phase8/2026-09-18-owner-supplied/link-title-check.json'
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=True, indent=2))
