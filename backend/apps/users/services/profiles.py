from apps.users.models import Profile


def get_or_create_profile(user):
    """Explicit lifecycle helper for future auth flows; avoids hidden signal writes."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile
