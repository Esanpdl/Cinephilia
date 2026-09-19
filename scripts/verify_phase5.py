"""Phase 5: numerical scoring and real Supabase/API integration checks.

Test accounts/interactions use a rollback-only transaction. No movies, source facts,
or model training data are created. Does not create/drop a hosted test database.
"""
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.movies.models import Movie
from apps.ratings.models import Rating, WatchlistItem
from apps.recommendations.services.hybrid.engine import HybridService
from apps.recommendations.services.hybrid.registry import catalog_snapshot, get_hybrid_service
from apps.recommendations.services.collaborative.registry import get_collaborative_service
from apps.recommendations.services.content.registry import get_content_service
from apps.recommendations.services.content.contracts import ContentIndexError
from apps.recommendations.services.collaborative.contracts import CollaborativeModelError
from apps.users.services.profiles import get_or_create_profile

WEIGHTS = {"content": .45, "collaborative": .40, "popularity": .15}
REPORT = {}
User = get_user_model()


class HybridMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = catalog_snapshot()[:5]
        assert len(cls.catalog) == 5
        cls.a, cls.b, cls.c, cls.d, cls.e = [row["tmdb_id"] for row in cls.catalog]

    def service(self, covered=True):
        content = SimpleNamespace(contains=lambda key: key != self.e, score_candidates=lambda seed, ids: {key: (.2 if key == self.b else .1) for key in ids})
        cf = SimpleNamespace(profile_status=lambda history: {"available": covered, "known_ratings": 3 if covered else 0}, score_candidates=lambda history, ids: {key: SimpleNamespace(normalized_score=.8) if covered and key != self.e else None for key in ids})
        return HybridService(content, cf, WEIGHTS)

    def test_weighted_arithmetic_and_relative_content_scaling(self):
        ranked, profile = self.service().rank({self.a: 8}, self.catalog)
        found = {entry.tmdb_id: entry for entry in ranked}
        value = found[self.b]
        maximum = max(math.log1p(row["popularity"]) for row in self.catalog)
        popularity = math.log1p(next(row["popularity"] for row in self.catalog if row["tmdb_id"] == self.b)) / maximum
        self.assertAlmostEqual(value.score, .45 * 1 + .40 * .8 + .15 * popularity)
        self.assertAlmostEqual(found[self.c].components["content"], .5)
        self.assertEqual(profile["mode"], "hybrid")

    def test_missing_item_coverage_is_not_a_zero_prediction(self):
        ranked, _ = self.service().rank({self.a: 8}, self.catalog)
        missing = next(entry for entry in ranked if entry.tmdb_id == self.e)
        self.assertIsNone(missing.components["content"])
        self.assertIsNone(missing.components["collaborative"])
        self.assertEqual(missing.effective_weights, {"content": 0, "collaborative": 0, "popularity": 1})

    def test_insufficient_history_redistributes_weights(self):
        ranked, profile = self.service(False).rank({self.a: 8}, self.catalog)
        found = next(entry for entry in ranked if entry.tmdb_id == self.b)
        self.assertAlmostEqual(found.effective_weights["content"], .45 / .60)
        self.assertFalse(profile["collaborative_available"])

    def test_cold_start_and_exclusions(self):
        ranked, profile = HybridService(None, None, WEIGHTS).rank({self.a: 2}, self.catalog, [self.b])
        self.assertEqual(profile["mode"], "popularity")
        self.assertNotIn(self.a, [entry.tmdb_id for entry in ranked])
        self.assertNotIn(self.b, [entry.tmdb_id for entry in ranked])
        self.assertTrue(all(entry.effective_weights["popularity"] == 1 for entry in ranked))

    def test_configuration_validation_and_disabled_models(self):
        for weights in ({**WEIGHTS, "content": -1}, {**WEIGHTS, "popularity": 0}, {**WEIGHTS, "content": float("nan")}):
            with self.assertRaises(ValueError):
                HybridService(None, None, weights)
        service = HybridService(SimpleNamespace(), SimpleNamespace(), {"content": 0, "collaborative": 0, "popularity": 3})
        ranked, _ = service.rank({}, self.catalog)
        self.assertEqual(len(ranked), 5)

    def test_deterministic_ties_empty_and_invalid_history(self):
        # Numeric score fixtures only; no movie facts are manufactured.
        service = HybridService(None, None, WEIGHTS)
        zeros = [{"tmdb_id": row["tmdb_id"], "popularity": 0} for row in self.catalog]
        ranked, _ = service.rank({}, zeros)
        self.assertEqual([entry.tmdb_id for entry in ranked], sorted(row["tmdb_id"] for row in zeros))
        self.assertEqual(service.rank({}, [])[0], [])
        with self.assertRaises(ValueError):
            service.rank({self.a: True}, self.catalog)

    def test_missing_artifacts_fall_back(self):
        with patch("apps.recommendations.services.hybrid.registry.get_content_service", side_effect=ContentIndexError), patch("apps.recommendations.services.hybrid.registry.get_collaborative_service", side_effect=CollaborativeModelError):
            service = get_hybrid_service()
        self.assertEqual(service.rank({}, self.catalog)[1]["mode"], "popularity")


class APITests(unittest.TestCase):
    def setUp(self):
        self.overrides = override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"], SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.addCleanup(self.rollback)
        cache.clear()
        self.password = "Phase5-validation-" + uuid.uuid4().hex
        self.username = "phase5_" + uuid.uuid4().hex[:16]
        self.user = User.objects.create_user(username=self.username, password=self.password)
        get_or_create_profile(self.user)
        self.client = APIClient(enforce_csrf_checks=True)
        self.ids = list(Movie.objects.order_by("tmdb_id").values_list("tmdb_id", flat=True)[:5])

    def rollback(self):
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def token(self, client=None):
        client = client or self.client
        response = client.get("/api/v1/users/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def sign_in(self):
        response = self.client.post("/api/v1/users/login/", {"username": self.username, "password": self.password}, format="json", HTTP_X_CSRFTOKEN=self.token())
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["csrf_token"]

    def test_anonymous_csrf_origin_and_login_rotation(self):
        data = {"username": self.username, "password": self.password}
        self.assertEqual(self.client.post("/api/v1/users/login/", data, format="json").status_code, 403)
        token = self.token()
        self.assertEqual(self.client.post("/api/v1/users/login/", data, format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://untrusted.example").status_code, 403)
        old_cookie = self.client.cookies["csrftoken"].value
        fresh = self.sign_in()
        self.assertNotEqual(old_cookie, self.client.cookies["csrftoken"].value)
        self.assertEqual(self.client.get("/api/v1/users/me/").json()["username"], self.username)
        self.assertEqual(self.client.post("/api/v1/users/logout/", HTTP_X_CSRFTOKEN=token).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/users/logout/", HTTP_X_CSRFTOKEN=fresh).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 403)

    def test_registration_password_privileges_and_duplicate(self):
        token = self.token()
        base = {"username": "register_" + uuid.uuid4().hex[:12], "password": self.password, "display_name": "Temporary test account", "is_staff": True}
        self.assertEqual(self.client.post("/api/v1/users/register/", base, format="json").status_code, 403)
        weak = self.client.post("/api/v1/users/register/", {**base, "password": "123"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(weak.status_code, 400)
        response = self.client.post("/api/v1/users/register/", base, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.content)
        created = User.objects.get(username=base["username"])
        self.assertTrue(created.check_password(self.password))
        self.assertFalse(created.is_staff)
        self.assertNotIn("password", response.json()["user"])
        other = APIClient(enforce_csrf_checks=True)
        duplicate = other.post("/api/v1/users/register/", base, format="json", HTTP_X_CSRFTOKEN=self.token(other))
        self.assertEqual(duplicate.status_code, 400)

    def test_login_rejects_invalid_and_throttles(self):
        token = self.token()
        for _ in range(10):
            result = self.client.post("/api/v1/users/login/", {"username": self.username, "password": "wrong"}, format="json", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(result.status_code, 400)
        result = self.client.post("/api/v1/users/login/", {"username": self.username, "password": "wrong"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code, 429)

    def test_public_search_detail_filters_and_query_bounds(self):
        response = self.client.get("/api/v1/movies/", {"q": "Godfather", "year": 1972})
        self.assertEqual(response.status_code, 200)
        self.assertIn(238, [entry["tmdb_id"] for entry in response.json()["results"]])
        detail = self.client.get("/api/v1/movies/238/")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["poster_url"].startswith("https://"))
        self.assertIn("youtube", detail.json()["trailer_embed_url"])
        self.assertFalse(detail.json()["is_technique_source"])
        self.assertEqual(self.client.get("/api/v1/movies/0/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/movies/genres/").status_code, 200)
        for params in ({"page_size": 999}, {"page": 0}, {"genre": "bad"}, {"year": 0}, {"ordering": "sql"}):
            self.assertEqual(self.client.get("/api/v1/movies/", params).status_code, 400)
        for size in (1, 20):
            with CaptureQueriesContext(connection) as queries:
                result = self.client.get("/api/v1/movies/", {"page_size": size})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(queries), 3)
        REPORT["catalog_list_queries"] = 3

    def test_rating_private_idempotent_validated_and_deleted(self):
        key = self.ids[0]
        path = f"/api/v1/ratings/{key}/"
        self.assertEqual(self.client.put(path, {"score": 8}, format="json").status_code, 403)
        csrf = self.sign_in()
        self.assertEqual(self.client.put(path, {"score": 8}, format="json").status_code, 403)
        for score in (0, 11, 1.5, True):
            self.assertEqual(self.client.put(path, {"score": score}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 400)
        self.assertEqual(self.client.put(path, {"score": 8, "user": self.user.pk + 1}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 201)
        self.assertEqual(self.client.put(path, {"score": 9}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(Rating.objects.filter(user=self.user, movie__tmdb_id=key).count(), 1)
        self.assertEqual(self.client.get(path).json()["score"], 9)
        self.assertEqual(self.client.get("/api/v1/ratings/").json()["count"], 1)
        other = User.objects.create_user(username="other_" + uuid.uuid4().hex[:12])
        outsider = APIClient(enforce_csrf_checks=True)
        outsider.force_login(other)
        self.assertEqual(outsider.get(path).status_code, 404)
        self.assertEqual(outsider.get("/api/v1/ratings/").json()["count"], 0)
        self.assertEqual(outsider.delete(path, HTTP_X_CSRFTOKEN=self.token(outsider)).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.delete(path, HTTP_X_CSRFTOKEN=csrf).status_code, 204)
        self.assertEqual(self.client.delete(path, HTTP_X_CSRFTOKEN=csrf).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_watchlist_ownership_duplicate_and_delete(self):
        csrf = self.sign_in()
        path = f"/api/v1/ratings/watchlist/{self.ids[0]}/"
        self.assertEqual(self.client.put(path, HTTP_X_CSRFTOKEN=csrf).status_code, 201)
        self.assertEqual(self.client.put(path, HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/ratings/watchlist/").json()["count"], 1)
        other = User.objects.create_user(username="watch_other_" + uuid.uuid4().hex[:12])
        outsider = APIClient(enforce_csrf_checks=True)
        outsider.force_login(other)
        self.assertEqual(outsider.get(path).status_code, 404)
        self.assertEqual(outsider.delete(path, HTTP_X_CSRFTOKEN=self.token(outsider)).status_code, 204)
        self.assertTrue(WatchlistItem.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.delete(path, HTTP_X_CSRFTOKEN=csrf).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_profile_permissions_and_genre_validation(self):
        csrf = self.sign_in()
        genre = Movie.objects.get(tmdb_id=238).genres.first()
        response = self.client.patch("/api/v1/users/me/profile/", {"is_film_student": True, "favorite_genres": [genre.tmdb_id], "display_name": "Test profile"}, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["favorite_genres"], [genre.tmdb_id])
        self.assertEqual(self.client.patch("/api/v1/users/me/profile/", {"favorite_genres": [0]}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 400)
        self.assertEqual(self.client.patch("/api/v1/users/me/profile/", {"bio": "a" * 2001}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 400)

    def test_real_hybrid_cold_start_then_ratings_and_no_stale_cache(self):
        self.assertEqual(self.client.get("/api/v1/recommendations/").status_code, 403)
        csrf = self.sign_in()
        cold = self.client.get("/api/v1/recommendations/", {"limit": 5})
        self.assertEqual(cold.status_code, 200, cold.content)
        self.assertEqual(cold.json()["profile"]["mode"], "popularity")
        evidence = json.loads((get_collaborative_service().directory / "evaluation.json").read_text())
        history = evidence["authentic_demo_profile"]["ratings"]
        for entry in history:
            result = self.client.put(f"/api/v1/ratings/{entry['tmdb_id']}/", {"score": entry["score"]}, format="json", HTTP_X_CSRFTOKEN=csrf)
            self.assertIn(result.status_code, (200, 201))
        started = time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/v1/recommendations/", {"limit": 20})
        elapsed = time.perf_counter() - started
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["profile"]["mode"], "hybrid")
        self.assertEqual(data["models"], {"content": True, "collaborative": True})
        self.assertEqual(len(data["results"]), 20)
        ids = [entry["movie"]["tmdb_id"] for entry in data["results"]]
        self.assertFalse(set(ids) & {entry["tmdb_id"] for entry in history})
        self.assertTrue(all(0 <= entry["score"] <= 1 for entry in data["results"]))
        self.assertEqual(len(queries), 6)  # session, user, ratings, watchlist, movies, genres
        query_count = len(queries)
        picked = ids[0]
        self.client.put(f"/api/v1/ratings/watchlist/{picked}/", HTTP_X_CSRFTOKEN=csrf)
        excluded = self.client.get("/api/v1/recommendations/", {"limit": 20}).json()
        self.assertNotIn(picked, [entry["movie"]["tmdb_id"] for entry in excluded["results"]])
        included = self.client.get("/api/v1/recommendations/", {"limit": 20, "exclude_watchlist": "false"}).json()
        self.assertIn(picked, [entry["movie"]["tmdb_id"] for entry in included["results"]])
        for entry in history:
            self.client.delete(f"/api/v1/ratings/{entry['tmdb_id']}/", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(self.client.get("/api/v1/recommendations/").json()["profile"]["mode"], "popularity")
        self.assertEqual(self.client.get("/api/v1/recommendations/", {"limit": 61}).status_code, 400)
        REPORT["real_hybrid"] = {"queries": query_count, "request_seconds": elapsed, "profile": data["profile"], "first_results": [{"tmdb_id": entry["movie"]["tmdb_id"], "title": entry["movie"]["title"], "score": entry["score"]} for entry in data["results"][:5]]}

    def test_openapi_and_documentation(self):
        schema = self.client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
        self.assertEqual(schema.status_code, 200)
        data = json.loads(schema.content)
        for path in ("/api/v1/users/login/", "/api/v1/movies/", "/api/v1/ratings/{tmdb_id}/", "/api/v1/ratings/watchlist/{tmdb_id}/", "/api/v1/recommendations/"):
            self.assertIn(path, data["paths"])
        self.assertEqual(data["components"]["securitySchemes"]["cookieAuth"]["in"], "cookie")
        docs = self.client.get("/api/docs/")
        self.assertEqual(docs.status_code, 200)
        self.assertIn(b'document.cookie.split', docs.content)
        self.assertIn(b'drf_spectacular_sidecar', docs.content)
        REPORT["openapi_paths"] = len(data["paths"])

    def test_private_response_headers_and_cors(self):
        self.sign_in()
        for path in ("/api/v1/users/me/", "/api/v1/ratings/", "/api/v1/ratings/watchlist/"):
            self.assertEqual(self.client.get(path)["Cache-Control"], "private, no-store")
        with override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"]):
            allowed = self.client.options("/api/v1/ratings/", HTTP_ORIGIN="http://localhost:5173", HTTP_ACCESS_CONTROL_REQUEST_METHOD="PUT")
            self.assertEqual(allowed["Access-Control-Allow-Origin"], "http://localhost:5173")
            self.assertEqual(allowed["Access-Control-Allow-Credentials"], "true")
            blocked = self.client.options("/api/v1/ratings/", HTTP_ORIGIN="https://untrusted.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="PUT")
            self.assertNotIn("Access-Control-Allow-Origin", blocked)

    def test_swagger_javascript_uses_rotated_cookie_without_cross_origin_leak(self):
        script = """
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = require('node:fs').readFileSync(0, 'utf8');
const document = {cookie: 'csrftoken=beforeLogin; sessionid=opaque'};
const window = {location: {href: 'http://localhost:8000/api/docs/', origin: 'http://localhost:8000'}};
const config = vm.runInNewContext('(' + source + ')', {URL, document, window});
function request(url, method='POST') { return config.requestInterceptor({url, method, headers: {}}); }
assert.equal(request('/api/v1/users/login/').headers['X-CSRFToken'], 'beforeLogin');
document.cookie = 'csrftoken=afterLogin; sessionid=opaque';
assert.equal(request('/api/v1/ratings/238/', 'PUT').headers['X-CSRFToken'], 'afterLogin');
assert.equal(request('https://untrusted.example/api/').headers['X-CSRFToken'], undefined);
assert.equal(request('/api/v1/movies/', 'GET').headers['X-CSRFToken'], undefined);
console.log('Swagger JavaScript CSRF checks passed');
"""
        result = subprocess.run(["node", "-e", script], input=settings.SPECTACULAR_SETTINGS["SWAGGER_UI_SETTINGS"], text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        REPORT["swagger_csrf_javascript"] = True


if __name__ == "__main__":
    before = {name: model.objects.count() for name, model in (("users", User), ("ratings", Rating), ("watchlist", WatchlistItem), ("movies", Movie))}
    get_content_service()
    get_collaborative_service()
    evidence = json.loads((get_collaborative_service().directory / "evaluation.json").read_text())
    demo = {entry["tmdb_id"]: entry["score"] for entry in evidence["authentic_demo_profile"]["ratings"]}
    service, catalog = get_hybrid_service(), catalog_snapshot()
    service.rank(demo, catalog)
    started = time.perf_counter()
    with CaptureQueriesContext(connection) as inference_queries:
        for _ in range(3):
            service.rank(demo, catalog)
        REPORT["pure_inference_queries"] = len(inference_queries)
        assert len(inference_queries) == 0
    REPORT["mean_hybrid_rank_ms_3_calls"] = (time.perf_counter() - started) * 1000 / 3
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (HybridMathTests, APITests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {name: model.objects.count() for name, model in (("users", User), ("ratings", Rating), ("watchlist", WatchlistItem), ("movies", Movie))}
    if before != after:
        raise AssertionError(f"Rollback verification failed: {before} != {after}")
    REPORT.update({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "database_counts_unchanged": before == after})
    (ROOT / "data/phase5").mkdir(exist_ok=True)
    (ROOT / "data/phase5/verification.json").write_text(json.dumps(REPORT, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(REPORT, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
