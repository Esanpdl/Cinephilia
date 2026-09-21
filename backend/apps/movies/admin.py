from django.contrib import admin
from .models import Movie, Genre, Person, MovieCredit


class MovieCreditInline(admin.TabularInline):
    model = MovieCredit
    extra = 0
    raw_id_fields = ["person"]


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ["title", "tmdb_id", "release_date", "vote_average", "vote_count", "catalog_rank"]
    search_fields = ["title", "original_title", "imdb_id", "tmdb_id"]
    list_filter = ["source_tags"]
    inlines = [MovieCreditInline]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "tmdb_id"]
    search_fields = ["name", "tmdb_id"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "tmdb_id"]
    search_fields = ["name", "tmdb_id"]
