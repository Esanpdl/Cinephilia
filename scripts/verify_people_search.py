"""Read-only search ordering checks against the authentic Supabase catalog."""
import json
import os
from pathlib import Path
import sys
import unittest
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.db import connection
from django.utils import timezone
from django.db.models import Q
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory
from apps.movies.models import Movie, MovieCredit
from apps.movies.views import MovieListView
from apps.movies.services.tmdb import write_json

REPORT = {}


class SearchTests(unittest.TestCase):
    def expected(self, term, ordering="-vote_average", year=None):
        titles = set(Movie.objects.filter(Q(title__icontains=term) | Q(original_title__icontains=term)).values_list("tmdb_id", flat=True))
        directors = set(MovieCredit.objects.filter(role="director", person__name__icontains=term).values_list("movie__tmdb_id", flat=True))
        actors = set(MovieCredit.objects.filter(role="cast", person__name__icontains=term).values_list("movie__tmdb_id", flat=True))
        ids = titles | directors | actors
        queryset = Movie.objects.filter(tmdb_id__in=ids)
        if year is not None:
            queryset = queryset.filter(release_date__year=year)
        order = ["title", "tmdb_id"] if ordering == "title" else ["-vote_average", "-vote_count", "tmdb_id"]
        ordered = list(queryset.order_by(*order).values_list("tmdb_id", flat=True))
        priority = lambda mid: 0 if mid in titles else 1 if mid in directors else 2
        return sorted(ordered, key=priority), priority

    def request(self, term, **params):
        with CaptureQueriesContext(connection) as captured:
            response = MovieListView.as_view()(APIRequestFactory().get("/api/v1/movies/", {"q": term, "page_size": 60, **params}, HTTP_HOST="127.0.0.1"))
            self.assertEqual(response.status_code, 200, response.data)
        return response.data, len(captured)

    def test_title_director_actor_order_and_no_duplicates(self):
        all_categories = set()
        for term in ["clint", "chaplin", "ford"]:
            expected, priority = self.expected(term)
            data, query_count = self.request(term)
            ids = [row["tmdb_id"] for row in data["results"]]
            self.assertEqual(ids, expected[:60])
            self.assertEqual(data["count"], len(expected))
            self.assertEqual(len(ids), len(set(ids)))
            self.assertLessEqual(query_count, 3)
            counts = Counter(priority(mid) for mid in expected)
            all_categories.update(counts)
            REPORT[term] = {"matches": len(expected), "categories": dict(counts), "queries": query_count}
        self.assertEqual(all_categories, {0, 1, 2})

    def test_secondary_sort_and_pagination(self):
        expected, _ = self.expected("ford", ordering="title")
        data, _ = self.request("ford", ordering="title")
        self.assertEqual([row["tmdb_id"] for row in data["results"]], expected[:60])
        self.assertGreater(len(expected), 60)
        second, _ = self.request("ford", ordering="title", page=2)
        self.assertEqual([row["tmdb_id"] for row in second["results"]], expected[60:120])

    def test_year_filter_applies_to_people_results(self):
        expected, _ = self.expected("clint", year=1992)
        data, _ = self.request("clint", year=1992)
        self.assertEqual([row["tmdb_id"] for row in data["results"]], expected[:60])
        self.assertTrue(expected)

    def test_empty_search_keeps_original_catalog_order(self):
        data, _ = self.request("")
        expected = list(Movie.objects.order_by("-vote_average", "-vote_count", "tmdb_id").values_list("tmdb_id", flat=True)[:60])
        self.assertEqual([row["tmdb_id"] for row in data["results"]], expected)

    def test_year_range_combines_with_people_priority_and_genre(self):
        ordered, _ = self.expected("clint")
        matching = set(Movie.objects.filter(tmdb_id__in=ordered, genres__tmdb_id=18).values_list("tmdb_id", flat=True))
        dates = dict(Movie.objects.filter(tmdb_id__in=ordered).values_list("tmdb_id", "release_date"))
        expected = [mid for mid in ordered if mid in matching and dates[mid] and 1970 <= dates[mid].year <= 1992]
        data, query_count = self.request("clint", year_from=1970, year_to=1992, genre=18)
        self.assertTrue(expected)
        self.assertEqual(data["count"], len(expected))
        self.assertEqual([row["tmdb_id"] for row in data["results"]], expected[:60])
        self.assertLessEqual(query_count, 3)

    def test_year_range_boundaries_and_single_year(self):
        current = timezone.now().year
        for params, start, end in [({"year_from": 1895, "year_to": current}, 1895, current), ({"year_to": 1900}, 1895, 1900), ({"year_from": current}, current, current), ({"year_from": 1972, "year_to": 1972}, 1972, 1972)]:
            data, _ = self.request("", **params)
            expected = [mid for mid, released in Movie.objects.order_by("-vote_average", "-vote_count", "tmdb_id").values_list("tmdb_id", "release_date") if released and start <= released.year <= end]
            self.assertEqual(data["count"], len(expected))
            self.assertEqual([row["tmdb_id"] for row in data["results"]], expected[:60])

    def test_invalid_year_ranges_return_field_errors(self):
        for params, field in [({"year_from": 1894}, "year_from"), ({"year_to": timezone.now().year + 1}, "year_to"), ({"year_from": 2000, "year_to": 1990}, "year_to"), ({"year": 1972, "year_from": 1970}, "year"), ({"year_from": "no-year"}, "year_from")]:
            response = MovieListView.as_view()(APIRequestFactory().get("/api/v1/movies/", params, HTTP_HOST="127.0.0.1"))
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SearchTests))
    write_json(ROOT / "data/phase7/search-verification.json", {"passed": result.wasSuccessful(), "checks": result.testsRun, "terms": REPORT})
    connection.close()
    sys.exit(0 if result.wasSuccessful() else 1)
