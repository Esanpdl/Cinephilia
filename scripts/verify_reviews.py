"""Exercise review permissions, real DB uniqueness, validation and rolling limits.

Temporary test users/reviews are rolled back; existing catalog facts are read only.
"""
import os
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient
from apps.movies.models import Movie
from apps.ratings.models import Rating, ReviewWriteQuota
from apps.ratings.views import OwnedReviewView, MovieReviewListView, RatingDetailView
from apps.movies.services.tmdb import write_json


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.user = get_user_model().objects.create_user(username="review_test_" + uuid.uuid4().hex[:12])
        self.other = get_user_model().objects.create_user(username="review_test_" + uuid.uuid4().hex[:12])
        self.movies = list(Movie.objects.order_by("tmdb_id")[:8])

    def tearDown(self):
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def call(self, method, payload=None, user=True, movie=None, view=OwnedReviewView):
        request = getattr(APIRequestFactory(), method)("/api/v1/ratings/reviews/", payload, format="json", HTTP_HOST="127.0.0.1")
        if user:
            force_authenticate(request, self.user if user is True else user)
        return view.as_view()(request, tmdb_id=(movie or self.movies[0]).tmdb_id)

    def test_public_read_private_write_and_csrf(self):
        self.assertEqual(self.call("get", user=False, view=MovieReviewListView).status_code, 200)
        self.assertEqual(self.call("put", {"stars": 4.5, "text": "A thoughtful film review."}, user=False).status_code, 403)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.put(f"/api/v1/ratings/reviews/{self.movies[0].tmdb_id}/mine/", {"stars": 4.5, "text": "A thoughtful film review."}, format="json", HTTP_HOST="127.0.0.1")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Rating.objects.filter(user=self.user).exists())

    def test_one_review_owner_edit_and_model_scale(self):
        first = self.call("put", {"stars": .5, "text": "A thoughtful film review."})
        self.assertEqual(first.status_code, 201, first.data)
        second = self.call("put", {"stars": 4.5, "text": "An edited thoughtful film review."})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Rating.objects.filter(user=self.user, movie=self.movies[0]).count(), 1)
        self.assertEqual(Rating.objects.get(user=self.user).score, 9)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(self.call("get", user=self.other).status_code, 404)
        self.call("delete", user=self.other)
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 1)
        public = self.call("get", user=False, view=MovieReviewListView).data["results"]
        self.assertEqual(public[0]["stars"], 4.5)
        self.assertNotIn("email", public[0])

    def test_invalid_stars_text_links_and_owner_fields(self):
        for stars in [0, 5.5, 1.2, 4.25, True]:
            self.assertEqual(self.call("put", {"stars": stars, "text": "A thoughtful film review."}).status_code, 400)
        for text in ["short", " " * 20, "x" * 3001, "Look at https://example.com for this film", "!!!!!!!!!!!!"]:
            self.assertEqual(self.call("put", {"stars": 5, "text": text}).status_code, 400)
        self.assertEqual(self.call("put", {"stars": 5, "text": "A thoughtful film review.", "user": self.other.pk}).status_code, 400)

    def test_duplicate_text_and_idempotent_save(self):
        payload = {"stars": 5, "text": "A thoughtful film review."}
        self.call("put", payload)
        for _ in range(6):
            self.assertEqual(self.call("put", payload).status_code, 200)
        self.assertEqual(len(ReviewWriteQuota.objects.get(user=self.user).recent_writes), 1)
        self.assertEqual(self.call("put", {**payload, "text": "A   THOUGHTFUL film review."}, movie=self.movies[1]).status_code, 400)

    def test_minute_limit_including_legacy_rating_and_delete(self):
        self.call("put", {"stars": 5, "text": "A thoughtful film review."})
        for score in [9, 8, 7, 6]:
            self.assertEqual(self.call("put", {"score": score}, view=RatingDetailView).status_code, 200)
        response = self.call("delete")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(self.call("delete", view=RatingDetailView).status_code, 429)
        self.assertTrue(Rating.objects.get(user=self.user).review_text)

    def test_daily_limit_and_deleting_preserves_quota_and_stars(self):
        self.call("put", {"stars": 3.5, "text": "A thoughtful film review."})
        self.assertEqual(self.call("delete").status_code, 204)
        rating = Rating.objects.get(user=self.user)
        self.assertEqual(rating.score, 7)
        self.assertEqual(rating.review_text, "")
        self.assertEqual(len(ReviewWriteQuota.objects.get(user=self.user).recent_writes), 2)
        old = timezone.now().timestamp() - 120
        ReviewWriteQuota.objects.filter(user=self.user).update(recent_writes=[old] * 20)
        self.assertEqual(self.call("put", {"stars": 5, "text": "A different film review."}).status_code, 429)

    def test_moderation_hides_text_and_blocks_delete_repost(self):
        self.call("put", {"stars": 5, "text": "A thoughtful film review."})
        Rating.objects.filter(user=self.user).update(review_hidden=True)
        self.assertEqual(self.call("get", user=False, view=MovieReviewListView).data["count"], 0)
        self.assertTrue(self.call("get").data["review_hidden"])
        self.assertEqual(self.call("put", {"stars": 4, "text": "An altered thoughtful review."}).status_code, 403)
        self.assertEqual(self.call("delete", view=RatingDetailView).status_code, 403)
        self.assertEqual(self.call("delete").status_code, 204)
        self.assertEqual(self.call("put", {"stars": 4, "text": "A reposted thoughtful review."}).status_code, 403)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests))
    write_json(ROOT / "data/expansion/review-api-verification.json", {"passed": result.wasSuccessful(), "checks": result.testsRun})
    connection.close()
    sys.exit(not result.wasSuccessful())
