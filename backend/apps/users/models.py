from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    watchlist_public = models.BooleanField(default=False)
    email_public = models.BooleanField(default=False)
    is_film_student = models.BooleanField(default=False)
    is_main_admin = models.BooleanField(default=False)
    favorite_genres = models.ManyToManyField("movies.Genre", blank=True, related_name="interested_profiles")
    favorite_actors = models.ManyToManyField("movies.Person", blank=True, related_name="actor_fans")
    favorite_directors = models.ManyToManyField("movies.Person", blank=True, related_name="director_fans")
    favorite_movies = models.ManyToManyField("movies.Movie", blank=True, related_name="favorite_profiles")
    favorite_eras = models.JSONField(default=list, blank=True)
    exploration = models.CharField(max_length=16, default="balanced")
    language_openness = models.CharField(max_length=16, default="any")
    preferred_languages = models.JSONField(default=list, blank=True)
    onboarding_status = models.CharField(max_length=16, default="not_required", choices=[
        ("not_required", "Existing account"), ("pending", "New account"), ("completed", "Completed")])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


def is_main_admin_user(user) -> bool:
    """Determine whether a user is the designated main administrator.
    
    Guards the main admin account even if the username is updated from 'admin'
    to a custom username.
    """
    if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", True):
        return False
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_main_admin and user.is_staff and user.is_superuser)
