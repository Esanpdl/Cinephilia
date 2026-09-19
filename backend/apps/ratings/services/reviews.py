"""Atomic owner-scoped reviews with shared PostgreSQL spam protection."""
from datetime import timedelta
import hashlib
import re
import unicodedata

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError, PermissionDenied

from ..models import Rating, ReviewWriteQuota


def review_digest(text):
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_review_text(text):
    text = unicodedata.normalize("NFKC", text).strip()
    if not 10 <= len(text) <= 3000 or sum(char.isalnum() for char in text) < 5:
        raise ValidationError("Write 10–3,000 characters, including at least five letters or numbers.")
    if re.search(r"(?:https?://|www\.|\b[\w-]+\.(?:com|net|org|io|dev|co|xyz|ru|cn|uk)\b)", text, re.I):
        raise ValidationError("Links are not allowed in reviews.")
    if any(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in text):
        raise ValidationError("Remove control characters from your review.")
    return text


def _lock_user(user):
    # Also serializes creation/deletion of ratings, so concurrent requests cannot
    # bypass the one-review rule or the per-user quota across server workers.
    get_user_model().objects.select_for_update().get(pk=user.pk)


def _consume_quota(user):
    now = timezone.now()
    quota, _ = ReviewWriteQuota.objects.get_or_create(user=user)
    recent = [value for value in quota.recent_writes if value > (now - timedelta(days=1)).timestamp()]
    minute = [value for value in recent if value > (now - timedelta(minutes=1)).timestamp()]
    if len(recent) >= 20:
        raise Throttled(wait=max(1, recent[0] + 86400 - now.timestamp()), detail="Review limit reached: 20 changes per 24 hours.")
    if len(minute) >= 5:
        raise Throttled(wait=max(1, minute[0] + 60 - now.timestamp()), detail="Please slow down: five review changes per minute.")
    quota.recent_writes = recent + [now.timestamp()]
    quota.save(update_fields=["recent_writes"])


@transaction.atomic
def save_rating(user, movie, score, text=None):
    _lock_user(user)
    rating = Rating.objects.filter(user=user, movie=movie).first()
    created = rating is None
    if rating is None:
        rating = Rating(user=user, movie=movie, score=score)
    next_text = rating.review_text if text is None else validate_review_text(text)
    if rating.review_hidden and next_text:
        raise PermissionDenied("This review has been hidden by a moderator and cannot be edited.")
    if not created and rating.score == score and rating.review_text == next_text:
        return rating, False
    if next_text:
        digest = review_digest(next_text)
        if Rating.objects.filter(user=user, review_digest=digest).exclude(movie=movie).exists():
            raise ValidationError({"text": "You already used this review on another film. Write about this film specifically."})
        _consume_quota(user)
        rating.review_text = next_text
        rating.review_digest = digest
        rating.review_updated_at = timezone.now()
    rating.score = score
    rating.save()
    return rating, created


@transaction.atomic
def remove_rating(user, movie, review_only=False):
    _lock_user(user)
    rating = Rating.objects.filter(user=user, movie=movie).first()
    if rating is None:
        return
    if rating.review_hidden and not review_only:
        raise PermissionDenied("A moderated review record cannot be deleted. You can remove its written text using the review controls.")
    if rating.review_text:
        _consume_quota(user)
    if not review_only:
        rating.delete()
    elif rating.review_text:
        rating.review_text = ""
        rating.review_digest = ""
        rating.review_updated_at = None
        # Preserve moderation status so delete/repost cannot unhide a review.
        rating.save(update_fields=["review_text", "review_digest", "review_updated_at", "updated_at"])
