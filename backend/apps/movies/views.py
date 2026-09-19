"""Search the imported catalog without live TMDB requests."""
from datetime import date
from django.db.models import F, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import Genre, Movie
from .serializers import GenreSerializer, MovieDetailSerializer, MovieQuerySerializer, MovieSummarySerializer
from .services.presentation import MediaContextMixin
from .services.queries import movie_details_queryset, search_catalog


class MovieDetailView(MediaContextMixin, RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = MovieDetailSerializer
    lookup_field = "tmdb_id"
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return movie_details_queryset()


@extend_schema(parameters=[MovieQuerySerializer])
class MovieListView(MediaContextMixin, ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = MovieSummarySerializer

    def get_queryset(self):
        params = MovieQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        movies = Movie.objects.prefetch_related("genres")
        if values.get("homepage"):
            movies = movies.filter(Q(source_tags__overlap=[Movie.Source.LETTERBOXD, Movie.Source.TSPDT, Movie.Source.ANIMATION, Movie.Source.BLACKWHITE]) | Q(curation_tags__len__gt=0), vote_count__gte=200)
        theme = values.get("theme")
        if theme in {"drama", "horror", "animation"}:
            movies = movies.filter(genres__tmdb_id={"drama": 18, "horror": 27, "animation": 16}[theme])
        elif theme == "blackwhite":
            movies = movies.filter(source_tags__contains=[Movie.Source.BLACKWHITE])
        elif theme == "international":
            movies = movies.exclude(original_language__in=["en", "", "xx", "zxx"])
        if values.get("q"):
            movies = search_catalog(movies, values["q"])
        if "genre" in values:
            movies = movies.filter(genres__tmdb_id=values["genre"])
        if "year" in values:
            movies = movies.filter(release_date__year=values["year"])
        if "year_from" in values or "year_to" in values:
            movies = movies.filter(
                release_date__gte=date(values.get("year_from", 1895), 1, 1),
                release_date__lt=date(values.get("year_to", timezone.now().year) + 1, 1, 1),
            )
        ordering = {"rating": ["-vote_average", "-vote_count", "tmdb_id"], "popularity": ["-popularity", "tmdb_id"], "newest": [F("release_date").desc(nulls_last=True), "tmdb_id"], "title": ["title", "tmdb_id"]}
        priority = ["search_priority"] if values.get("q") else []
        return movies.order_by(*priority, *ordering[values["ordering"]])


class GenreListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GenreSerializer
    pagination_class = None
    queryset = Genre.objects.order_by("name", "tmdb_id")
