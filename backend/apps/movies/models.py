"""Canonical TMDB catalog; technique provenance is recorded, never inferred."""
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class Genre(models.Model):
    tmdb_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Person(models.Model):
    tmdb_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=300)
    profile_path = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Movie(models.Model):
    class Source(models.TextChoices):
        TMDB = "tmdb", "TMDB catalog"
        LETTERBOXD = "letterboxd_top1000", "Letterboxd scraped list"
        TSPDT = "tspdt_top1000", "TSPDT scraped list"
        ANIMATION = "letterboxd_animation250", "Letterboxd Top 250 Animation"
        BLACKWHITE = "letterboxd_blackwhite100", "Letterboxd Black and White"

    tmdb_id = models.PositiveIntegerField(unique=True)
    imdb_id = models.CharField(max_length=20, blank=True, db_index=True)
    title = models.CharField(max_length=500, db_index=True)
    original_title = models.CharField(max_length=500, blank=True)
    overview = models.TextField(blank=True)
    tagline = models.TextField(blank=True)
    release_date = models.DateField(null=True, blank=True, db_index=True)
    original_language = models.CharField(max_length=20, blank=True)
    runtime = models.PositiveIntegerField(null=True, blank=True)
    vote_average = models.DecimalField(max_digits=5, decimal_places=3)
    vote_count = models.PositiveIntegerField()
    popularity = models.FloatField(default=0)
    poster_path = models.CharField(max_length=255, blank=True)
    backdrop_path = models.CharField(max_length=255, blank=True)
    trailer_key = models.CharField(max_length=32, blank=True)
    trailer_name = models.CharField(max_length=500, blank=True)
    trailer_official = models.BooleanField(default=False)
    keywords = models.JSONField(default=list, blank=True)
    source_tags = ArrayField(models.CharField(max_length=32, choices=Source.choices), default=list)
    curation_tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    genres = models.ManyToManyField(Genre, related_name="movies", blank=True)
    people = models.ManyToManyField(Person, through="MovieCredit", related_name="movies")
    catalog_rank = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    tmdb_synced_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-vote_average", "-vote_count", "tmdb_id"]
        indexes = [
            models.Index(fields=["-vote_average", "-vote_count"], name="movie_rating_votes_idx"),
            GinIndex(fields=["source_tags"], name="movie_sources_gin"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(vote_average__gte=0, vote_average__lte=10), name="movie_vote_average_range"),
        ]

    @property
    def is_technique_source(self):
        return bool(set(self.source_tags) & {self.Source.LETTERBOXD, self.Source.TSPDT, self.Source.ANIMATION, self.Source.BLACKWHITE})

    @property
    def is_homepage_eligible(self):
        return self.is_technique_source or bool(self.curation_tags)

    def __str__(self):
        return self.title


class MovieCredit(models.Model):
    class Role(models.TextChoices):
        CAST = "cast", "Cast"
        DIRECTOR = "director", "Director"

    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="credits")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="credits")
    tmdb_credit_id = models.CharField(max_length=64)
    role = models.CharField(max_length=10, choices=Role.choices)
    character = models.TextField(blank=True)
    cast_order = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["movie", "tmdb_credit_id"], name="unique_movie_credit")]
        indexes = [models.Index(fields=["movie", "role", "cast_order"], name="credit_movie_role_order_idx")]
