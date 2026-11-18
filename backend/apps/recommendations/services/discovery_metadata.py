"""Filter metadata that cannot explain a narrative recommendation on its own."""
GENERIC_KEYWORDS = frozenset({
    'excited', 'exciting', 'excitement', 'adoring', 'admiring', 'adorable',
    'amused', 'cheerful', 'awestruck', 'enthusiastic', 'inspirational',
    'duringcreditsstinger', 'aftercreditsstinger', '3d', 'imax', '4dx',
    'based on novel or book', 'based on true story', 'woman director',
    'independent film', 'sequel', 'remake', 'short film',
})


def meaningful_keywords(movie):
    return {k['tmdb_id']: k['name'] for k in movie.get('keywords', [])
            if k['name'].strip().casefold() not in GENERIC_KEYWORDS}


def semantic_document(movie):
    # No title, cast or director identity: semantic matches should follow the story.
    return '\n'.join(['Genres: ' + ', '.join(g['name'] for g in movie.get('genres', [])),
                      'Story: ' + movie.get('overview', ''),
                      'Themes: ' + ', '.join(meaningful_keywords(movie).values())])
