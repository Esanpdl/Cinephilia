"""Confirm PostgreSQL serializes simultaneous review writes across connections."""
import os
from pathlib import Path
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from apps.movies.models import Movie
from apps.ratings.models import Rating, ReviewWriteQuota
from apps.ratings.services.reviews import save_rating
from apps.movies.services.tmdb import write_json
from rest_framework.exceptions import Throttled

user = get_user_model().objects.create_user(username="review_concurrency_" + uuid.uuid4().hex[:12])
movie = Movie.objects.order_by("tmdb_id").first()

def save(index):
    close_old_connections()
    try:
        save_rating(user, movie, index + 1, f"Temporary concurrent test review number {index}.")
        return "saved"
    except Throttled:
        return "throttled"
    finally:
        connection.close()

try:
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(save, range(7)))
    assert results.count("saved") == 5, results
    assert results.count("throttled") == 2, results
    assert Rating.objects.filter(user=user, movie=movie).count() == 1
    assert len(ReviewWriteQuota.objects.get(user=user).recent_writes) == 5
    write_json(ROOT / "data/expansion/review-concurrency-verification.json", {"passed": True, "parallel_connections": 3, "attempts": 7, "saved": 5, "throttled": 2, "review_rows": 1})
    print("Concurrency verified: one review row; exactly five writes accepted, two throttled.")
finally:
    user.delete()
    connection.close()
