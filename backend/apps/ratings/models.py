from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="movie_ratings")
    movie = models.ForeignKey("movies.Movie", on_delete=models.CASCADE, related_name="user_ratings")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    review_text = models.TextField(blank=True, default="", max_length=3000)
    review_digest = models.CharField(max_length=64, blank=True, default="")
    review_updated_at = models.DateTimeField(null=True, blank=True)
    review_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "movie"], name="unique_user_movie_rating"),
            models.CheckConstraint(condition=models.Q(score__gte=1, score__lte=10), name="rating_score_range"),
        ]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="rating_user_updated_idx"),
            models.Index(fields=["user", "review_digest"], name="review_user_digest_idx"),
            models.Index(fields=["movie", "-review_updated_at"], name="review_movie_date_idx"),
        ]


class ReviewWriteQuota(models.Model):
    """At most 20 successful review mutations per user in a rolling 24 hours."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    recent_writes = models.JSONField(default=list)


class WatchlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlist_items")
    movie = models.ForeignKey("movies.Movie", on_delete=models.CASCADE, related_name="watchlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "movie"], name="unique_user_watchlist_movie")]
        indexes = [models.Index(fields=["user", "-created_at"], name="watchlist_user_created_idx")]
