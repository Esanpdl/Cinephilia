"""Make contact sheets of real cached frames for source/technique review."""
import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tmdb-id', type=int, action='append', required=True)
args = parser.parse_args()
directory = ROOT / 'data/phase8/review'
directory.mkdir(exist_ok=True)
for mid in args.tmdb_id:
    data = json.loads((ROOT / f'data/phase8/analysis/{mid}.json').read_text(encoding='utf-8'))
    frames = data['all_frames']
    sheet = Image.new('RGB', (1200, math.ceil(len(frames) / 4) * 190), '#171717')
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        x, y = (i % 4) * 300, (i // 4) * 190
        image = Image.open(ROOT / 'data/phase8/frames' / frame['image'])
        thumb = ImageOps.contain(image, (296, 160))
        sheet.paste(thumb, (x + (300-thumb.width)//2, y))
        draw.text((x+5, y+163), f"{frame['index']:03} | {frame['timestamp']:.2f}s | {mid}", fill='white')
    sheet.save(directory / f'{mid}.jpg')
    print(directory / f'{mid}.jpg')
