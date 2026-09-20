from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from apps.movies.models import Movie
from apps.recommendations.serializers import RecommendationQuerySerializer
from apps.recommendations.views import RecommendationView

User = get_user_model()


class RecommendationOffsetTests(TestCase):
    def test_query_serializer_offset(self):
        serializer = RecommendationQuerySerializer(data={"limit": 10, "offset": 20})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["offset"], 20)

    def test_query_serializer_default_offset(self):
        serializer = RecommendationQuerySerializer(data={"limit": 10})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["offset"], 0)

    def test_query_serializer_refresh_seed_valid(self):
        serializer = RecommendationQuerySerializer(data={"limit": 24, "refresh_seed": "seed_123"})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["refresh_seed"], "seed_123")

    def test_query_serializer_refresh_seed_blank(self):
        serializer = RecommendationQuerySerializer(data={"limit": 24, "refresh_seed": ""})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["refresh_seed"], "")

    def test_query_serializer_refresh_seed_too_long(self):
        serializer = RecommendationQuerySerializer(data={"limit": 24, "refresh_seed": "x" * 129})
        self.assertFalse(serializer.is_valid())
        self.assertIn("refresh_seed", serializer.errors)

    def test_query_serializer_limit_up_to_100(self):
        serializer = RecommendationQuerySerializer(data={"limit": 100})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["limit"], 100)

    def test_query_serializer_limit_exceeds_100(self):
        serializer = RecommendationQuerySerializer(data={"limit": 101})
        self.assertFalse(serializer.is_valid())
        self.assertIn("limit", serializer.errors)

