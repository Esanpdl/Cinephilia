"""Request-local content/CF recommendations; no persistent preference writes."""
import math
from .discovery import MODES, diversify


def rank_selection(selected, catalog_ids, content, collaborative, history=None, excluded=(), discovery='balanced', metadata=None):
    if discovery not in MODES:
        raise ValueError('Unknown discovery mode.')
    history = history or {}
    blocked = set(selected) | set(history) | set(excluded)
    candidates = sorted(set(catalog_ids)-blocked)
    # A modest positive proxy is needed to fold an ephemeral profile into SVD.
    # Explicit saved ratings always override that proxy, especially dislikes.
    temporary = {key: 8 for key in selected}
    temporary.update(history)
    seeds = [key for key in selected if history.get(key, 8) >= 7 and content and content.contains(key)]
    content_values, closest, per_seed = {}, {}, {}
    if seeds:
        covered = [key for key in candidates if content.contains(key)]
        for seed in seeds:
            values = content.score_discovery(seed, covered, MODES[discovery]['fields']) if hasattr(content, 'score_discovery') else content.score_candidates(seed, covered)
            for key, value in values.items():
                per_seed.setdefault(key, []).append(value)
                if key not in closest or value > closest[key][1]:
                    closest[key] = (seed, value)
        for key, values in per_seed.items():
            strongest = sorted(values, reverse=True)[:2]
            content_values[key] = .65 * sum(strongest)/len(strongest) + .35 * sum(values)/len(seeds)
    status = collaborative.profile_status(temporary) if collaborative else {'available': False}
    cf_values = collaborative.score_candidates(temporary, candidates) if status['available'] else {}
    strongest_content = max(content_values.values(), default=0.)
    ranked = []
    for key in candidates:
        c = content_values.get(key)
        cf = cf_values.get(key)
        f = cf.normalized_score if cf else None
        if (c is None or c <= 0) and f is None:
            continue
        # A strong general CF prior must not turn an almost unrelated indexed film
        # into a discovery pick. Missing content coverage remains an explicit fallback.
        if c is not None and strongest_content > 0 and c < .25 * strongest_content:
            continue
        weights = {'content': 0.6 if c is not None else 0.0, 'collaborative': 0.4 if f is not None else 0.0}
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        score = weights['content']*(c or 0)+weights['collaborative']*(f or 0)
        if not math.isfinite(score) or not 0 <= score <= 1.000001:
            raise ValueError('Invalid selection recommendation score.')
        ranked.append({'tmdb_id': key, 'match_percentage': round(min(1, score)*100),
                       'score': score, 'components': {'content': c, 'collaborative': f}, 'effective_weights': weights})
    ranked.sort(key=lambda r: (-r['score'], r['tmdb_id']))
    if metadata is None:
        metadata = {}
        for mid in [*selected, *candidates]:
            if content and content.contains(mid):
                movie = content.movie(mid)
                metadata[mid] = {field: {p['id'] for p in movie.get(field, [])} for field in ('directors', 'genres')}
    results, relaxed = diversify(ranked, seeds or selected, metadata, discovery)
    seed_directors = set().union(*(set(metadata.get(mid, {}).get('directors', ())) for mid in (seeds or selected)))
    for entry in results:
        reasons = []
        match = closest.get(entry['tmdb_id'])
        if match and match[1] > 0:
            explanation = content.explain_discovery(match[0], entry['tmdb_id'], MODES[discovery]['fields']) if hasattr(content, 'explain_discovery') else content.explain(match[0], entry['tmdb_id'])
            title = content.movie(match[0])['title']
            shared = explanation.get('shared', {})
            for field, label in [('keywords', 'story keywords'), ('genres', 'genres'), ('cast', 'cast')]:
                names = shared.get(field, [])[:2]
                if names and explanation.get('contributions', {}).get(field, 1) > 0:
                    reasons.append(f"Shares {label} ({', '.join(names)}) with {title}.")
            if not reasons:
                keywords = shared.get('keywords', [])[:2]
                if keywords:
                    reasons.append(f"Shares story keywords ({', '.join(keywords)}) with {title}.")
                elif explanation.get('contributions', {}).get('semantic', 0) > 0:
                    reasons.append(f'Its story description is semantically similar to {title}.')
                elif explanation.get('contributions', {}).get('overview', 0) > 0:
                    reasons.append(f'Its synopsis shares descriptive themes and terms with {title}.')
                else:
                    reasons.append(f'Shares film characteristics with {title}.')
        if entry['components']['collaborative'] is not None:
            reasons = reasons[:2]+['Audience rating patterns suggest this film fits the taste reflected in your selections.']
        directors = set(metadata.get(entry['tmdb_id'], {}).get('directors', ()))
        if seed_directors and directors and not directors & seed_directors:
            content_reasons = [r for r in reasons if not r.startswith('Audience rating patterns')]
            reasons = content_reasons[:1] + (['Audience rating patterns support this suggestion.'] if entry['components']['collaborative'] is not None else content_reasons[1:2]) + ['Introduces a director outside your selected films.']
        entry['explanations'] = reasons[:3]
    models = {'content': bool(seeds), 'collaborative': bool(status['available']), 'semantic': bool(seeds and getattr(content, 'model_name', None))}
    notes = []
    if relaxed:
        notes.append('Director diversity was relaxed because too few similarly strong alternatives were available.')
    if not models['collaborative']:
        notes.append('There is not enough audience-rating coverage for these choices, so film similarities guide these suggestions.')
    if not models['content']:
        notes.append('Detailed film similarities are unavailable for these choices; supported audience-rating predictions are used where possible.')
    if any(history.get(key, 8) < 7 for key in selected):
        notes.append('Your saved low ratings take precedence over selected favourites.')
    if len(results)<3:
        notes.append('Fewer than three supported, unseen matches are available. Try a different selection.')
    return {'results': results, 'models': models, 'selected_count': len(selected), 'discovery': discovery, 'notice': ' '.join(notes),
            'score_note': 'Taste match combines film similarities and audience rating patterns where available. It is a relative match score, not a probability that you will enjoy the film.'}
