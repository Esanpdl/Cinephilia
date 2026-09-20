"""Read-only catalog representation, ready for Phase 5's API views."""
from rest_framework import serializers
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from config.api import PageQuerySerializer

from apps.movies.models import Movie
from apps.movies.services.media import image_url, trailer_embed_url


class GenreSerializer(serializers.Serializer):
    tmdb_id = serializers.IntegerField()
    name = serializers.CharField()


class DirectorSerializer(serializers.Serializer):
    tmdb_id = serializers.IntegerField()
    name = serializers.CharField()


class CastSerializer(DirectorSerializer):
    character = serializers.CharField()
    order = serializers.IntegerField(allow_null=True)


class MovieSummarySerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    poster_url = serializers.SerializerMethodField()
    trailer_embed_url = serializers.SerializerMethodField()
    is_technique_source = serializers.BooleanField(read_only=True)
    is_homepage_eligible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Movie
        fields = ["tmdb_id", "title", "release_date", "original_language", "vote_average", "vote_count", "genres", "poster_url", "trailer_embed_url", "is_technique_source", "is_homepage_eligible"]
        read_only_fields = fields

    def get_poster_url(self, movie) -> str | None:
        return image_url(movie.poster_path, self.context["tmdb_configuration"])

    def get_trailer_embed_url(self, movie) -> str | None:
        return trailer_embed_url(movie.trailer_key)


class MovieQuerySerializer(PageQuerySerializer):
    homepage = serializers.BooleanField(required=False, help_text="Only approved scraped/requested films with at least 200 TMDB votes.")
    theme = serializers.ChoiceField(choices=["drama", "horror", "animation", "blackwhite", "international"], required=False)
    q = serializers.CharField(max_length=200, required=False, allow_blank=True, help_text="Search title, director or actor. Title matches rank first, then directors, then actors; ordering breaks ties within each group.")
    genre = serializers.IntegerField(min_value=1, required=False, help_text="TMDB genre ID.")
    year = serializers.IntegerField(min_value=1895, required=False, help_text="Exact release year; 1895 through the current year. Cannot combine with a range.")
    year_from = serializers.IntegerField(min_value=1895, required=False, help_text="Inclusive first release year; defaults to 1895 when only year_to is supplied.")
    year_to = serializers.IntegerField(min_value=1895, required=False, help_text="Inclusive last release year; defaults to the current year when only year_from is supplied.")
    ordering = serializers.ChoiceField(choices=["rating", "popularity", "newest", "title"], default="rating")

    def validate(self, attrs):
        current_year = timezone.now().year
        errors = {field: f"Use a year from 1895 through {current_year}." for field in ("year", "year_from", "year_to") if attrs.get(field, 1895) > current_year}
        if errors:
            raise serializers.ValidationError(errors)
        if "year" in attrs and ("year_from" in attrs or "year_to" in attrs):
            raise serializers.ValidationError({"year": "Use either an exact year or a year range."})
        if attrs.get("year_from", 1895) > attrs.get("year_to", current_year):
            raise serializers.ValidationError({"year_to": "End year must be the same as or later than start year."})
        return attrs


class FeaturedMovieQuerySerializer(serializers.Serializer):
    seed = serializers.CharField(max_length=128, required=False, allow_blank=True, help_text="Deterministic seed for repeatable selection.")


class MovieDetailSerializer(serializers.ModelSerializer):
    genres = serializers.SerializerMethodField()
    cast = serializers.SerializerMethodField()
    directors = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    backdrop_url = serializers.SerializerMethodField()
    trailer_embed_url = serializers.SerializerMethodField()
    is_technique_source = serializers.BooleanField(read_only=True)
    letterboxd_embed_url = serializers.SerializerMethodField()
    is_homepage_eligible = serializers.BooleanField(read_only=True)
    community_rating = serializers.SerializerMethodField()
    community_rating_count = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "tmdb_id", "imdb_id", "title", "original_title", "overview", "tagline",
            "release_date", "original_language", "runtime", "vote_average", "vote_count",
            "genres", "keywords", "cast", "directors", "poster_path", "poster_url",
            "backdrop_path", "backdrop_url", "trailer_key", "trailer_name", "trailer_official",
            "trailer_embed_url", "letterboxd_embed_url", "source_tags", "is_technique_source", "is_homepage_eligible", "catalog_rank", "tmdb_synced_at",
            "community_rating", "community_rating_count",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_community_rating(self, movie) -> float | None:
        if hasattr(movie, "community_score_avg"):
            avg = movie.community_score_avg
        else:
            from django.db.models import Avg
            avg = movie.user_ratings.aggregate(Avg("score"))["score__avg"]
        return round(float(avg) / 2.0, 1) if avg is not None else None

    @extend_schema_field(serializers.IntegerField())
    def get_community_rating_count(self, movie) -> int:
        if hasattr(movie, "community_rating_count"):
            return movie.community_rating_count
        return movie.user_ratings.count()

    def get_letterboxd_embed_url(self, movie) -> str:
        return f"https://embed.letterboxd.com/tmdb/{movie.tmdb_id}/embed-histogram/?theme=dark&noTitle=true"

    @extend_schema_field(GenreSerializer(many=True))
    def get_genres(self, movie):
        return [{"tmdb_id": genre.tmdb_id, "name": genre.name} for genre in movie.genres.all()]


    @extend_schema_field(CastSerializer(many=True))
    def get_cast(self, movie):
        credits = [credit for credit in movie.credits.all() if credit.role == "cast"]
        credits.sort(key=lambda credit: (credit.cast_order is None, credit.cast_order or 0, credit.pk))
        return [{"tmdb_id": credit.person.tmdb_id, "name": credit.person.name, "character": credit.character, "order": credit.cast_order} for credit in credits]

    @extend_schema_field(DirectorSerializer(many=True))
    def get_directors(self, movie):
        return [{"tmdb_id": credit.person.tmdb_id, "name": credit.person.name} for credit in movie.credits.all() if credit.role == "director"]

    def get_poster_url(self, movie) -> str | None:
        return image_url(movie.poster_path, self.context["tmdb_configuration"])

    def get_backdrop_url(self, movie) -> str | None:
        return image_url(movie.backdrop_path, self.context["tmdb_configuration"], kind="backdrop", preferred_size="w1280")

    def get_trailer_embed_url(self, movie) -> str | None:
        return trailer_embed_url(movie.trailer_key)
