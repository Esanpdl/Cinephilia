"""Study material projected from already-published evidence; never creates labels."""
import hashlib
from django.core.cache import cache
from django.db.models import Count, Max, JSONField
from django.db.models.expressions import RawSQL
from ..models import TrailerAnalysis, StudyCard, Technique

SHOT_TERMS = {
    'extreme_close_up': ('extreme-close-up', 'Extreme close-up', 'A small facial feature or subject detail occupies most of the image.'),
    'close_up': ('close-up', 'Close-up', 'The face or principal subject fills much of the image, with little surrounding context.'),
    'medium_close_up': ('medium-close-up', 'Medium close-up', 'The principal person is framed approximately from the chest or shoulders upward.'),
    'medium': ('medium-shot', 'Medium shot', 'The principal person is framed approximately from the waist upward.'),
    'full': ('full-shot', 'Full shot', 'The principal person is visible from head to feet.'),
    'wide': ('wide-framing', 'Wide framing', 'The surroundings occupy a large part of the image relative to its subjects.'),
}
COLOUR_TERMS = frozenset(('monochrome', 'muted-color', 'saturated-color', 'tonal-contrast'))


def taxonomy():
    from config.public_cache import revision
    key = 'study-taxonomy:' + str(revision())
    cached = cache.get(key)
    if cached is not None:
        return cached
    terms = {t['slug']: t for t in Technique.objects.values('slug', 'name', 'category', 'description', 'automatic')}
    for slug, name, description in SHOT_TERMS.values():
        terms.setdefault(slug, dict(slug=slug, name=name, category='Framing', description=description, automatic=False))
    cache.set(key, terms, 120)
    return terms


def frame_cards(row, terms):
    for frame in row['frames']:
        annotation = frame.get('technique_analysis') or {}
        source = annotation.get('source')
        if source not in ('human', 'model'):
            continue
        slugs = set(annotation.get('tags', []))
        shot = SHOT_TERMS.get(annotation.get('shot_scale'))
        if shot:
            slugs.add(shot[0])
        for slug in sorted(slugs & terms.keys()):
            technique = terms[slug]
            key = hashlib.sha256(f"{row['movie__tmdb_id']}:{frame['image']}:{slug}".encode()).hexdigest()[:32]
            yield dict(id='frame-' + key, tmdb_id=row['movie__tmdb_id'], title=row['movie__title'],
                       technique=technique, timestamp=frame.get('timestamp'), image_url='/api/v1/cinematography/frames/' + frame['image'],
                       explanation=technique['description'], evidence='reviewed' if source == 'human' else 'model',
                       source_url=row['source_url'])


def published_cards():
    from config.public_cache import revision
    key = 'study-catalog-v2:' + str(revision())
    cached = cache.get(key)
    if cached is not None:
        return cached
    ready = TrailerAnalysis.objects.filter(status='ready')
    approved = StudyCard.objects.filter(approved=True, analysis__status='ready')
    terms = taxonomy()
    rows = {}
    # Gallery exclusions also govern virtual cards. This reads published annotations
    # only: the new review proposals never enter this service.
    # Project only labels and image identity in PostgreSQL, not 19k full pixel
    # measurement records, across the remote database connection.
    projected = RawSQL("""(SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'image', f->'image', 'timestamp', f->'timestamp', 'technique_analysis', f->'technique_analysis')), '[]'::jsonb)
        FROM jsonb_array_elements(frames) AS f
        WHERE f->'technique_analysis'->>'shot_scale' IS NOT NULL
           OR COALESCE(jsonb_array_length(f->'technique_analysis'->'tags'), 0) > 0)""", [], output_field=JSONField())
    for row in ready.annotate(published_frames=projected).values('movie__tmdb_id', 'movie__title', 'source_url', 'published_frames'):
        row['frames'] = row.pop('published_frames')
        for card in frame_cards(row, terms):
            rows[(card['tmdb_id'], card['image_url'], card['technique']['slug'])] = card
    for card in approved.values('pk', 'image', 'technique__slug', 'timestamp', 'explanation', 'evidence',
                                'analysis__movie__tmdb_id', 'analysis__movie__title', 'analysis__version', 'analysis__source_url'):
        url = '/api/v1/cinematography/frames/' + card['image']
        identity = (card['analysis__movie__tmdb_id'], url, card['technique__slug'])
        rows[identity] = dict(id=str(card['pk']), tmdb_id=identity[0], title=card['analysis__movie__title'],
            technique=terms[card['technique__slug']], timestamp=None if card['analysis__version'].startswith('supplied-stills') else card['timestamp'],
            image_url=url, explanation=card['explanation'], evidence=card['evidence'], source_url=card['analysis__source_url'])
    result = sorted(rows.values(), key=lambda c: (c['title'].casefold(), c['image_url'], c['technique']['slug']))
    cache.set(key, result, 120)
    return result


def filter_cards(cards, *, source='all', category='all', technique='', q=''):
    evidence = {'human': 'reviewed', 'model': 'model', 'measured': 'measured'}.get(source)
    return [card for card in cards if (not evidence or card['evidence'] == evidence)
            and (not technique or card['technique']['slug'] == technique)
            and (not q or q.casefold() in card['title'].casefold())
            and (category == 'all' or (card['technique']['slug'] in COLOUR_TERMS) == (category == 'color'))]
