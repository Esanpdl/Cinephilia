"""Deterministic sampled-frame analysis. No cuts, pacing or optical flow.

All metrics describe retained trailer samples, never whole-film technique frequency.
OpenCV is an offline dependency; importing HTTP services does not load it.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import threading

import cv2
import numpy as np

VERSION = 'palette-text-2.1'
_local = threading.local()


def crop_borders(frame):
    """Remove contiguous nearly-black outer bars, retaining at least 60% per axis."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rows = np.mean(gray < 18, axis=1) > .97
    cols = np.mean(gray < 18, axis=0) > .97
    h, w = gray.shape
    top = bottom = left = right = 0
    while top < h * .2 and rows[top]:
        top += 1
    while bottom < h * .2 and rows[h - 1 - bottom]:
        bottom += 1
    while left < w * .2 and cols[left]:
        left += 1
    while right < w * .2 and cols[w - 1 - right]:
        right += 1
    return frame[top:h-bottom, left:w-right], [left, top, w-right, h-bottom]


def frame_metrics(frame, mask=None):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    chroma = np.ptp(frame.astype(np.int16), axis=2)
    if mask is not None:
        gray, hsv, chroma = gray[mask], hsv[mask], chroma[mask]
    eligible = (gray > 20) & (gray < 240)
    colored = float((chroma[eligible] > 12).mean()) if eligible.any() else 0
    brightness = float(gray.mean() / 255)
    saturation = float(hsv[..., 1].mean() / 255)
    contrast = float((np.percentile(gray, 90) - np.percentile(gray, 10)) / 255)
    return {'brightness': round(brightness, 4), 'saturation': round(saturation, 4),
            'contrast': round(contrast, 4), 'colored_pixel_fraction': round(colored, 4),
            'monochrome': colored < .025}


def reject_frame(frame):
    """Conservative graphics/fade heuristic; text over footage may remain."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if np.percentile(gray, 95) < 22:
        return 'black_or_fade'
    if np.percentile(gray, 5) > 238:
        return 'white_or_flash'
    if gray.std() < 9:
        return 'flat_graphic'
    # Title/end cards typically have a nearly uniform dominant background.
    pixels = cv2.resize(frame, (96, 54)).reshape(-1, 3)
    bins = (pixels // 24).astype(np.int32)
    labels = bins[:, 0] * 121 + bins[:, 1] * 11 + bins[:, 2]
    if np.bincount(labels).max() / len(labels) > .70:
        return 'likely_title_or_graphic'
    return None


def color_mode(metrics):
    if not metrics:
        return 'unknown'
    fraction = sum(m['monochrome'] for m in metrics) / len(metrics)
    return 'black_and_white' if fraction >= .95 else 'mixed' if fraction >= .15 else 'color'


def visual_pixels(frame, mask=None):
    pixels = frame[mask] if mask is not None else frame.reshape(-1, 3)
    return pixels[np.linspace(0, len(pixels) - 1, min(2304, len(pixels)), dtype=int)]


def palette(frames, masks=None):
    pixels = np.concatenate([visual_pixels(f, masks[i] if masks is not None else None) for i, f in enumerate(frames)])
    # Perceptual Lab clustering; deterministic seed and fixed sample sizes.
    lab = cv2.cvtColor(pixels.reshape(1, -1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(42)
    _, labels, centers = cv2.kmeans(lab, 6, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5), 1, cv2.KMEANS_PP_CENTERS)
    colors = cv2.cvtColor(np.uint8(np.clip(centers, 0, 255)).reshape(1, -1, 3), cv2.COLOR_LAB2RGB)[0]
    counts = np.bincount(labels.ravel(), minlength=6)
    order = np.argsort(-counts)
    return [{'hex': '#' + ''.join(f'{int(c):02x}' for c in colors[i]), 'weight': round(float(counts[i] / len(pixels)), 4)} for i in order]


def technique_observations(metrics):
    """Observable measurements, deliberately avoiding semantic technique claims."""
    found = []
    if metrics['monochrome']:
        found.append(('monochrome', 'This sampled frame has almost no channel-to-channel color variation. Study how light and dark areas separate the forms.'))
    elif metrics['saturation'] > .38:
        found.append(('saturated-color', 'The retained image area has strong measured color saturation. Notice where the most vivid colors draw attention.'))
    elif metrics['saturation'] < .15:
        found.append(('muted-color', 'The retained image area has low measured saturation. Compare the subdued colors with the brighter and darker areas.'))
    if metrics['contrast'] > .65:
        found.append(('tonal-contrast', 'The sampled frame has a wide separation between its darker and lighter pixels. Look at where those tones meet.'))
    return found


def analyze(path, movie, metadata, output, samples=48):
    path, output = Path(path), Path(output)
    cap = cv2.VideoCapture(str(path))
    cv2.setNumThreads(1)
    fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if not cap.isOpened() or fps <= 0 or count < 2:
        cap.release()
        raise ValueError('Unreadable video or missing timing metadata')
    duration = count / fps
    if not 5 <= duration <= 1200:
        cap.release()
        raise ValueError('Video duration is outside review limits')
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    target = output / str(movie['tmdb_id']) / digest[:12]
    target.mkdir(parents=True, exist_ok=True)
    frames, kept, excluded = [], [], Counter()
    last_hashes = []
    try:
        for index, seconds in enumerate(np.linspace(duration * .07, duration * .9, samples)):
            frame_index = min(int(seconds * fps), int(count) - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, original = cap.read()
            if not ok:
                excluded['decode_failed'] += 1
                continue
            original = cv2.resize(original, (min(768, original.shape[1]), max(1, round(original.shape[0] * min(768, original.shape[1]) / original.shape[1]))))
            cropped, bounds = crop_borders(original)
            small = cv2.resize(cropped, (384, max(1, round(cropped.shape[0] * 384 / cropped.shape[1]))))
            rejection = reject_frame(small)
            if rejection:
                excluded[rejection] += 1
                continue
            # Duplicate suppression reduces repeated promotional stills; not cut detection.
            tiny = cv2.cvtColor(cv2.resize(small, (9, 8)), cv2.COLOR_BGR2GRAY)
            dhash = tiny[:, 1:] > tiny[:, :-1]
            if any(np.count_nonzero(dhash != previous) < 4 for previous in last_hashes):
                excluded['near_duplicate'] += 1
                continue
            last_hashes.append(dhash)
            metrics = frame_metrics(small)
            name = f'{index:03d}.jpg'
            if not cv2.imwrite(str(target / name), cropped, [cv2.IMWRITE_JPEG_QUALITY, 88]):
                raise ValueError('Could not write representative frame')
            kept.append({'index': index, 'timestamp': round(frame_index / fps, 3),
                         'image': f'{movie["tmdb_id"]}/{digest[:12]}/{name}',
                         'crop': bounds, 'metrics': metrics})
            frames.append(small)
    finally:
        cap.release()
    if len(kept) < 5:
        raise ValueError(f'Only {len(kept)} usable frames; insufficient visual evidence')
    metrics = [frame['metrics'] for frame in kept]
    aggregated = {key: round(float(np.mean([m[key] for m in metrics])), 4) for key in ['brightness', 'saturation', 'contrast', 'colored_pixel_fraction']}
    # A normalized HSV histogram is a transparent palette-only similarity vector.
    histogram = np.zeros((12, 4, 4), np.float64)
    for frame in frames:
        hsv = cv2.cvtColor(cv2.resize(frame, (64, 36)), cv2.COLOR_BGR2HSV)
        histogram += cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256])
    histogram = histogram.ravel()
    histogram /= histogram.sum()
    selected = np.linspace(0, len(kept) - 1, min(6, len(kept)), dtype=int)
    cards = []
    used = set()
    for frame in kept:
        for slug, explanation in technique_observations(frame['metrics']):
            if slug not in used:
                cards.append({'technique': slug, 'explanation': explanation, 'evidence': 'measured', **frame})
                used.add(slug)
    result = {'version': VERSION, 'tmdb_id': movie['tmdb_id'], 'title': movie['title'], 'year': movie['year'],
            'source_sha256': digest, 'source_url': metadata.get('source_url', movie['trailer_url']),
            'source_title': metadata.get('video_title', ''), 'duration': round(duration, 3),
            'sample_count': samples, 'retained_count': len(kept), 'excluded': dict(excluded),
            'color_mode': color_mode(metrics), 'metrics': aggregated, 'palette': palette(frames),
            'vector': histogram.round(7).tolist(), 'frames': [kept[i] for i in selected],
            'study_cards': cards, 'all_frames': kept,
            'scope': 'Retained trailer samples; not whole-film measurements.',
            'screening': 'Uniform-border, fade, graphic and duplicate heuristics.'}
    return refine_text_masks(result, output)


def text_mask(frame):
    """Detect text polygons without transcribing dialogue or storing text."""
    if not hasattr(_local, 'ocr'):
        from rapidocr_onnxruntime import RapidOCR
        _local.ocr = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1,
                             det_limit_side_len=768, det_limit_type='max', use_cls=False, use_rec=False)
    boxes, _ = _local.ocr(frame, use_cls=False, use_rec=False)
    excluded = np.zeros(frame.shape[:2], dtype=np.uint8)
    boxes = boxes or []
    for box in boxes:
        cv2.fillPoly(excluded, [np.asarray(box, dtype=np.int32)], 255)
    # Include anti-aliased text edges and subtitle shadows, not just letter centers.
    excluded = cv2.dilate(excluded, np.ones((7, 7), np.uint8))
    return excluded == 0, boxes


def refine_text_masks(data, frame_root):
    frames, masks, kept = [], [], []
    excluded = Counter(data.get('excluded', {}))
    for record in data['all_frames']:
        frame = cv2.imread(str(Path(frame_root) / record['image']))
        if frame is None:
            raise ValueError('A cached evidence frame is missing; rerun with --force.')
        mask, boxes = text_mask(frame)
        text_fraction = 1 - float(mask.mean())
        if text_fraction > .30 or (len(boxes) >= 10 and text_fraction > .12):
            excluded['text_dominated'] += 1
            continue
        # Reject title cards whose remaining background is nearly uniform after masking.
        remaining_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[mask]
        if len(remaining_gray) < 1024 or (boxes and remaining_gray.std() < 15):
            excluded['text_on_flat_background'] += 1
            continue
        metrics = frame_metrics(frame, mask)
        kept.append({**record, 'metrics': metrics, 'text_excluded_fraction': round(text_fraction, 4),
                     'text_regions': (np.asarray(boxes) / [frame.shape[1], frame.shape[0]]).round(5).tolist() if boxes else []})
        frames.append(frame)
        masks.append(mask)
    if len(kept) < 5:
        raise ValueError('Fewer than five visual frames remain after text masking.')
    metrics = [frame['metrics'] for frame in kept]
    histogram = np.zeros((12, 4, 4), np.float64)
    for frame, mask in zip(frames, masks):
        pixels = visual_pixels(frame, mask)
        hsv = cv2.cvtColor(pixels.reshape(1, -1, 3), cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256])
        histogram += hist / hist.sum()  # Every retained frame has equal influence.
    vector = histogram.ravel() / histogram.sum()
    selected = np.linspace(0, len(kept) - 1, min(6, len(kept)), dtype=int)
    cards, used = [], set()
    # Prefer clear, minimally overlaid evidence for study cards.
    for frame in sorted(kept, key=lambda f: f['text_excluded_fraction']):
        for slug, explanation in technique_observations(frame['metrics']):
            if slug not in used:
                cards.append({'technique': slug, 'explanation': explanation, 'evidence': 'measured', **frame})
                used.add(slug)
    data.update(version=VERSION, color_mode=color_mode(metrics), retained_count=len(kept), excluded=dict(excluded),
                palette=palette(frames, masks), vector=vector.round(7).tolist(), frames=[kept[i] for i in selected],
                all_frames=kept, study_cards=cards,
                metrics={key: round(float(np.mean([m[key] for m in metrics])), 4) for key in ['brightness', 'saturation', 'contrast', 'colored_pixel_fraction']},
                text_masking={'method': 'RapidOCR PP-OCR text detector; polygon masks expanded by 3 pixels',
                              'mean_excluded_fraction': round(float(np.mean([f['text_excluded_fraction'] for f in kept])), 4),
                              'frames_with_detected_text': sum(bool(f['text_regions']) for f in kept),
                              'limitations': 'Detection may miss stylized lettering or non-text logos. Text inside the scene is also masked conservatively.'},
                screening='Black bars, fades, flat graphics, duplicate frames and text-dominated cards excluded; detected text pixels masked in all color measurements.')
    return data
