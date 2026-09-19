from django.db.models import Case, Exists, IntegerField, OuterRef, Prefetch, Q, Value, When

from apps.movies.models import Movie, MovieCredit


def search_catalog(movies, query):
    """Title first, then director, then cast; EXISTS never duplicates movies."""
    title = Q(title__icontains=query) | Q(original_title__icontains=query)
    credits = MovieCredit.objects.filter(movie_id=OuterRef("pk"), person__name__icontains=query)
    director = Exists(credits.filter(role=MovieCredit.Role.DIRECTOR))
    actor = Exists(credits.filter(role=MovieCredit.Role.CAST))
    return movies.filter(title | director | actor).alias(
        search_priority=Case(
            When(title, then=Value(0)), When(director, then=Value(1)),
            default=Value(2), output_field=IntegerField(),
        ),
    )


def movie_details_queryset():
    """Three queries for any page of details, including genres, cast and directors."""
    return Movie.objects.prefetch_related(
        "genres", Prefetch("credits", queryset=MovieCredit.objects.select_related("person")),
    )
