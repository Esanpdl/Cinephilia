"""Build paged contact sheets from every retained frame of flagged sources."""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'data/phase8'
report = json.loads((base / 'inventory-verification.json').read_text(encoding='utf-8'))
out = base / 'review/sources'
out.mkdir(parents=True, exist_ok=True)
index = []
for item in report['source_review_needed']:
    mid = item['tmdb_id']
    data = json.loads((base / f'analysis/{mid}.json').read_text(encoding='utf-8'))
    frames = data['all_frames']
    sheet = Image.new('RGB', (1200, 65 + math.ceil(len(frames) / 6) * 132), '#171717')
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 5), f"{mid}: {data['title']} | {data['duration']}s", fill='white')
    draw.text((8, 25), data['source_title'], fill='white')
    draw.text((8, 45), data['source_url'], fill='white')
    for i, frame in enumerate(frames):
        x, y = i % 6 * 200, 65 + i // 6 * 132
        with Image.open(base / 'frames' / frame['image']) as source:
            thumb = ImageOps.contain(source, (196, 108))
            sheet.paste(thumb, (x + (200-thumb.width)//2, y))
        draw.text((x+4, y+110), f"{frame['index']:03} | {frame['timestamp']:.2f}s", fill='white')
    sheet.save(out / f'{mid}.jpg')
    index.append({'id': mid, 'title': data['title'], 'video': data['source_title'], 'seconds': data['duration'], 'frames': len(frames), 'url':data['source_url']})
print(json.dumps(index, ensure_ascii=True, indent=2))
