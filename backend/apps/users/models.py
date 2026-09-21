from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    is_film_student = models.BooleanField(default=False)
    is_main_admin = models.BooleanField(default=False)
    favorite_genres = models.ManyToManyField("movies.Genre", blank=True, related_name="interested_profiles")
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
    if profile and getattr(profile, "is_main_admin", False):
        return True
    if getattr(user, "is_superuser", False) and user.get_username() == "admin":
        return True
    if getattr(user, "email", "").lower() == "esan3125@gmail.com" and getattr(user, "is_staff", False):
        return True
    return False
