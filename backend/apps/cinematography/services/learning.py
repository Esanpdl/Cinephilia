"""Evidence retrieval and palette-only similarity, independent of core ranking."""
from datetime import date
import hashlib
import math
from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Max, Prefetch
from django.db.models.fields.json import KeyTransform
from apps.cinematography.models import TrailerAnalysis, StudyCard, TechniqueSubmission
from .colour_distance import load_signature, similarity_matrix, DIMENSIONS, VERSION as COLOUR_VERSION


def analyses(summary=False):
    query = TrailerAnalysis.objects.select_related('movie').defer('vector').prefetch_related(
        Prefetch('study_cards', queryset=StudyCard.objects.filter(approved=True).select_related('technique', 'analysis__movie').defer('analysis__frames', 'analysis__vector', 'analysis__quality')),
        Prefetch('movie__technique_submissions', queryset=TechniqueSubmission.objects.filter(status='approved').select_related('technique', 'movie'), to_attr='published_observations'))
    return query.annotate(preview_frame=KeyTransform('0', 'frames')).defer('frames') if summary else query


def palette_index():
    """Cache perceptual colour signatures; status/import changes change the key."""
    ready = TrailerAnalysis.objects.filter(status='ready')
    revision = ready.aggregate(updated=Max('updated_at'), count=Count('pk'))
    key = 'visual-palettes:' + COLOUR_VERSION + ':' + hashlib.sha256(str(revision).encode()).hexdigest()
    result = cache.get(key)
    if result is None:
        result = []
        for row in ready.values('movie__tmdb_id', 'source_sha256', 'quality__palette_method'):
            data = load_signature(settings.BASE_DIR.parent, row['movie__tmdb_id'], row['source_sha256'], row['quality__palette_method'], film_only=True)
            result.append((row['movie__tmdb_id'], data['film'] if data is not None else None))
        cache.set(key, result, 60)
    return result


def visual_candidates():
    """Retrieve compact evidence rather than all study-card objects and credits."""
    from config.public_cache import revision
    key = 'visual-candidates-v1:' + str(revision())
    result = cache.get(key)
    if result is not None:
        return result
    rows = list(TrailerAnalysis.objects.filter(status='ready').select_related('movie').annotate(
        preview_frame=KeyTransform('0', 'frames')).only('movie_id', 'movie__tmdb_id', 'movie__title',
        'movie__release_date', 'movie__poster_path', 'selection_rank', 'status', 'reason', 'color_mode', 'palette', 'quality'))
    lookup = {row.pk: row for row in rows}
    terms = {row.pk: set() for row in rows}
    for aid, slug, evidence in StudyCard.objects.filter(approved=True, analysis_id__in=lookup).values_list('analysis_id', 'technique__slug', 'evidence').distinct():
        if evidence != 'measured' or lookup[aid].quality.get('source_kind') != 'owner-supplied-stills':
            terms[aid].add(slug)
    community = {}
    for mid, slug in TechniqueSubmission.objects.filter(status='approved').values_list('movie_id', 'technique__slug').distinct():
        community.setdefault(mid, set()).add(slug)
    result = []
    for row in rows:
        known = terms[row.pk] | community.get(row.movie_id, set())
        if row.quality.get('source_kind') == 'owner-supplied-stills':
            known |= set(row.quality.get('measured_observation_slugs', [])) | set(row.quality.get('human_observation_slugs', []))
        result.append((row, known, model_observation_slugs(row)))
    cache.set(key, result, 120)
    return result


def observation_slugs(analysis):
    cards = {c.technique.slug for c in analysis.study_cards.all()} if analysis.status == 'ready' else set()
    if analysis.status == 'ready' and analysis.quality.get('source_kind') == 'owner-supplied-stills':
        cards = {c.technique.slug for c in analysis.study_cards.all() if c.evidence != 'measured'}
        cards |= set(analysis.quality.get('measured_observation_slugs', []))
        cards |= set(analysis.quality.get('human_observation_slugs', []))
    return cards | {t.technique.slug for t in analysis.movie.published_observations}


def model_observation_slugs(analysis):
    return set(analysis.quality.get('model_observation_slugs', [])) if analysis.status == 'ready' else set()


def visual_similarity(palette, left_terms, right_terms, left_model=None, right_model=None):
    """Describe available evidence explicitly; missing measurements never become zero."""
    technique = round(100 * len(left_terms & right_terms) / len(left_terms | right_terms), 1) if left_terms and right_terms else None
    components = {'palette': palette, 'techniques': technique}
    weights = {'palette': .75, 'techniques': .25}
    available = {key: weights[key] for key, value in components.items() if value is not None}
    total = sum(available.values())
    effective = {key: round(weight / total, 4) for key, weight in available.items()} if total else {}
    # Suggestions can adjust established evidence by at most five score points.
    # They never generate a recommendation by themselves or amplify missing tags.
    model = None
    if total and left_model and right_model:
        model = round(100 * len(left_model & right_model) / len(left_model | right_model), 1)
        effective = {key: value * .95 for key, value in effective.items()}
        effective['model_suggestions'] = .05
    components['model_suggestions'] = model
    return {'score': round(sum(components[key] * weight for key, weight in effective.items()), 1) if total else None,
            'components': components, 'weights': effective,
            'scope': 'All-frame colour and measured/human-reviewed technique overlap. Model suggestions contribute at most 5%, require at least three frames and 20% of the collection, and never score alone. Unlabelled frames contribute no technique evidence. These are similarity scores, not accuracy estimates.'}


def palette_similarity(a, b):
    if a is None or b is None or len(a) == 0 or len(a) != len(b):
        return None
    if len(a) == DIMENSIONS:
        return round(float(similarity_matrix(a, b)[0, 0]) * 100, 1)
    return round(min(100, sum(math.sqrt(max(0, x) * max(0, y)) for x, y in zip(a, b)) * 100), 1)


def week_key(today=None):
    iso = (today or date.today()).isocalendar()
    return f'{iso.year}-W{iso.week:02}'


def weekly_choice(ids, today=None):
    if not ids:
        return None
    # Deterministic for a given ISO week and eligible set, without fake engagement.
    return min(ids, key=lambda mid: hashlib.sha256(f'{week_key(today)}:{mid}'.encode()).hexdigest())
