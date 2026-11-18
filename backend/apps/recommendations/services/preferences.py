"""Content and metadata taste ranking, without manufactured rating history."""
from dataclasses import dataclass
from django.contrib.postgres.aggregates import ArrayAgg
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Count, Max, Value, CharField
from apps.movies.models import Movie, MovieCredit
from apps.users.services.profiles import get_or_create_profile
from .hybrid.engine import HybridScore


def taste_catalog():
    revision = Movie.objects.aggregate(updated=Max('updated_at'), count=Count('pk'))
    key = f"recommendations:taste-catalog:v2:{revision['count']}:{revision['updated']}"
    rows = cache.get(key)
    if rows is None:
        rows = {m['id']: {**m, 'genres': set(), 'cast': set(), 'directors': set()}
                for m in Movie.objects.order_by('tmdb_id').values('id', 'tmdb_id', 'release_date', 'original_language')}
        for item in Movie.objects.values('id').annotate(ids=ArrayAgg('genres__tmdb_id', distinct=True, filter=Q(genres__tmdb_id__isnull=False))).values('id', 'ids'):
            if item['id'] in rows:
                rows[item['id']]['genres'].update(item['ids'] or [])
        for item in MovieCredit.objects.values('movie_id').annotate(
            cast=ArrayAgg('person__tmdb_id', distinct=True, filter=Q(role=MovieCredit.Role.CAST)),
            directors=ArrayAgg('person__tmdb_id', distinct=True, filter=Q(role=MovieCredit.Role.DIRECTOR)),
        ).values('movie_id', 'cast', 'directors'):
            if item['movie_id'] in rows:
                rows[item['movie_id']]['cast'].update(item['cast'] or [])
                rows[item['movie_id']]['directors'].update(item['directors'] or [])
        rows = {m['tmdb_id']: m for m in rows.values()}
        cache.set(key, rows, settings.HYBRID_CATALOG_CACHE_SECONDS)
    return rows


@dataclass(frozen=True)
class TasteScore(HybridScore):
    reasons: tuple = ()


def overlap(a, b):
    return len(a & b)/len(a | b) if a and b else 0.0


def score_preferences(preferences, catalog, content=None):
    """Pure ranking signals: missing content artifacts retain metadata matching."""
    favourites = [catalog[k] for k in preferences['movies'] if k in catalog]
    content_scores = {}
    if content and favourites:
        seeds = [m['tmdb_id'] for m in favourites if content.contains(m['tmdb_id'])]
        covered = [k for k in catalog if content.contains(k)]
        for seed in seeds:
            for key, value in content.score_candidates(seed, covered).items():
                content_scores[key] = max(content_scores.get(key, 0.0), value)
    ranges = [tuple(map(int, value.split('-'))) for value in preferences['eras']]
    result = {}
    for key, movie in catalog.items():
        signals, reasons = [], []
        for selected, field, weight, reason in [
            (preferences['genres'], 'genres', 2.0, 'Matches your favourite genres'),
            (preferences['actors'], 'cast', 2.5, 'Features one of your favourite actors'),
            (preferences['directors'], 'directors', 3.0, 'Directed by one of your favourites'),
        ]:
            if selected:
                hit = len(selected & movie[field])/min(len(selected), max(1, len(movie[field])))
                signals.append((weight, hit))
                if hit:
                    reasons.append(reason)
        if ranges:
            year = movie['release_date'].year if movie['release_date'] else None
            hit = float(year is not None and any(start <= year <= end for start, end in ranges))
            signals.append((1.5, hit))
            if hit:
                reasons.append('From an era you enjoy')
        if favourites:
            # Structured fallback helps films absent from the active TF-IDF index.
            similarity = max((0.6*overlap(movie['genres'], seed['genres']) +
                              0.25*bool(movie['directors'] & seed['directors']) +
                              0.15*overlap(movie['cast'], seed['cast']) for seed in favourites), default=0)
            similarity = max(similarity, content_scores.get(key, 0))
            signals.append((4.0, similarity))
            if similarity > 0:
                reasons.append('Shares film characteristics with your favourites')
        score = sum(w*v for w, v in signals)/sum(w for w, _ in signals) if signals else 0.0
        if preferences['language_openness']=='prefer' and preferences['languages']:
            # A soft preference never eliminates all international suggestions.
            if movie['original_language'] in preferences['languages']:
                if score > 0:
                    score = min(1, score*1.1)
                    reasons.append('In a language you prefer')
            else:
                score *= 0.7
        result[key] = (score, tuple(reasons))
    return result


def starter_weight(history, watchlist):
    """Ten ratings or twenty saves reduce explicit preferences to a 15% influence.

    A saved-and-rated movie counts only as a rating. Repeated page views,
    re-rating the same film and refresh clicks do not increase evidence.
    """
    evidence = len(history) + 0.5*len(set(watchlist)-set(history))
    return max(0.15, 1.0-evidence/10.0)


def apply_preferences(user, history, ranked, profile_summary, content, watchlist=()):
    profile = get_or_create_profile(user)
    preference_weight = starter_weight(history, watchlist)
    summary = {**profile_summary, 'watchlist_movies': len(set(watchlist)), 'preference_weight': 0.0}
    if profile.onboarding_status == 'pending':
        # A user may leave setup and resume voluntarily later. Do not substitute
        # popular films for the requested personalized first recommendations.
        if history or watchlist:
            return ranked, summary
        return [], {**summary, 'mode': 'preferences'}
    if profile.onboarding_status != 'completed':
        return ranked, summary
    names = ['genres', 'actors', 'directors', 'movies']
    preferences = {name: set() for name in names}
    # One round trip for all four preference relations; important on a remote DB.
    relations = [getattr(profile, 'favorite_'+name).order_by().annotate(
        preference_kind=Value(name, output_field=CharField())).values_list('preference_kind', 'tmdb_id') for name in names]
    for name, identity in relations[0].union(*relations[1:], all=True):
        preferences[name].add(identity)
    preferences.update(eras=profile.favorite_eras, language_openness=profile.language_openness,
                       languages=set(profile.preferred_languages))
    catalog = taste_catalog()
    scores = score_preferences(preferences, catalog, content)
    # Genuine activity gradually restores the original hybrid ranking. No
    # synthetic ratings or watchlist entries; mature users retain a modest floor.
    result = []
    for entry in ranked:
        if entry.tmdb_id in preferences['movies']:
            continue
        taste, reasons = scores.get(entry.tmdb_id, (0.0, ()))
        if not history and not watchlist and taste <= 0:
            continue
        score = preference_weight*taste + (1-preference_weight)*entry.score
        components = {**entry.components, 'preferences': taste}
        weights = {**{k: v*(1-preference_weight) for k, v in entry.effective_weights.items()}, 'preferences': preference_weight}
        result.append(TasteScore(entry.tmdb_id, score, components, weights, reasons[:3]))
    result.sort(key=lambda x: (-x.score, x.tmdb_id))
    # Comfort-zone setting controls genre repetition in the first selection,
    # while every cold-start candidate still has positive preference evidence.
    penalty = preference_weight*{'familiar': 0.0, 'balanced': 0.04, 'adventurous': 0.12}[profile.exploration]
    if penalty and result:
        pool, tail = result[:200], result[200:]
        chosen, counts = [], {}
        while pool:
            def adjusted(entry):
                genres = catalog.get(entry.tmdb_id, {}).get('genres', set())
                repetition = sum(counts.get(g, 0) for g in genres)/max(len(genres), 1)
                return entry.score/(1+penalty*repetition), -entry.tmdb_id
            winner = max(pool, key=adjusted)
            pool.remove(winner)
            chosen.append(winner)
            for genre in catalog.get(winner.tmdb_id, {}).get('genres', set()):
                counts[genre] = counts.get(genre, 0)+1
        result = chosen+tail
    return result, {**summary, 'mode': 'preferences', 'preference_weight': preference_weight}
