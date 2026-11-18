"""Explicit discovery policies, not learned accuracy or invented cinematic labels."""
MODES = {
    'familiar': {'fields': {'overview': .20, 'keywords': .20, 'genres': .25, 'cast': .15, 'directors': .20}, 'redundancy': .04, 'novelty': 0., 'seed_director_limit': 2},
    'balanced': {'fields': {'overview': .40, 'keywords': .30, 'genres': .20, 'cast': .05, 'directors': .05}, 'redundancy': .12, 'novelty': .08, 'seed_director_limit': 1},
    'adventurous': {'fields': {'overview': .55, 'keywords': .35, 'genres': .10, 'cast': 0., 'directors': 0.}, 'redundancy': .20, 'novelty': .20, 'seed_director_limit': 0},
}


def overlap(a, b):
    return len(a & b) / len(a | b) if a and b else 0.


def diversify(ranked, selected, metadata, mode):
    if not ranked:
        return [], False
    policy = MODES[mode]
    def field(mid, key):
        return set(metadata.get(mid, {}).get(key, ()))
    seed_directors = set().union(*(field(mid, 'directors') for mid in selected))
    seed_genres = set().union(*(field(mid, 'genres') for mid in selected))
    languages = {metadata.get(mid, {}).get('original_language') for mid in selected} - {None, ''}
    def year(mid):
        value = metadata.get(mid, {}).get('release_date')
        return value.year if hasattr(value, 'year') else int(str(value)[:4]) if value else None
    years = [year(mid) for mid in selected if year(mid) is not None]
    # Diversity must not replace an evidenced match with an arbitrary distant film.
    pool = [r for i, r in enumerate(ranked) if i < 3 or r['score'] >= ranked[0]['score'] * .60]
    chosen, used_directors = [], set()
    repeated_seeds = 0
    relaxed = False
    for level in range(3):
        while len(chosen) < 3:
            candidates = []
            for entry in pool:
                if entry in chosen:
                    continue
                mid = entry['tmdb_id']
                directors = field(mid, 'directors')
                from_seed = bool(directors & seed_directors)
                if level < 2 and from_seed and repeated_seeds >= policy['seed_director_limit']:
                    continue
                if level == 0 and directors & used_directors:
                    continue
                genres = field(mid, 'genres')
                redundancy = max((overlap(genres, field(r['tmdb_id'], 'genres')) for r in chosen), default=0.)
                novelty = 1 - overlap(genres, seed_genres) if genres and seed_genres else 0.
                language = metadata.get(mid, {}).get('original_language')
                language_novelty = float(bool(languages and language and language not in languages))
                era_novelty = min(1., min(abs(year(mid)-y) for y in years)/30) if years and year(mid) else 0.
                novelty = .5*novelty + .25*language_novelty + .25*era_novelty
                utility = entry['score'] - policy['redundancy'] * redundancy + policy['novelty'] * novelty
                candidates.append((utility, entry))
            if not candidates:
                break
            _, best = max(candidates, key=lambda item: (item[0], item[1]['score'], -item[1]['tmdb_id']))
            chosen.append(best)
            directors = field(best['tmdb_id'], 'directors')
            used_directors |= directors
            repeated_seeds += bool(directors & seed_directors)
            relaxed |= level > 0
        if len(chosen) == 3:
            break
    return chosen, relaxed
