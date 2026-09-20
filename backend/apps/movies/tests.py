from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.movies.models import Movie
from apps.movies.serializers import MovieDetailSerializer
from apps.movies.services.queries import movie_details_queryset
from apps.ratings.models import Rating

User = get_user_model()


class MovieCommunityRatingTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(
            tmdb_id=9999991,
            title="Test Movie For Community Rating",
            vote_average=8.5,
            vote_count=100,
            popularity=10.0,
            tmdb_synced_at="2026-01-01T00:00:00Z"
        )
        self.user1 = User.objects.create_user(username="testuser1", password="password123")
        self.user2 = User.objects.create_user(username="testuser2", password="password123")

    def test_community_rating_empty(self):
        movie = movie_details_queryset().get(tmdb_id=self.movie.tmdb_id)
        serializer = MovieDetailSerializer(movie, context={"tmdb_configuration": {"images": {"secure_base_url": "https://image.tmdb.org/t/p/"}}})
        self.assertIsNone(serializer.data["community_rating"])
        self.assertEqual(serializer.data["community_rating_count"], 0)

    def test_community_rating_with_ratings(self):
        # score 9 = 4.5 stars, score 10 = 5.0 stars. Average score = 9.5 -> 4.75 -> round(9.5/2, 1) = 4.8
        Rating.objects.create(user=self.user1, movie=self.movie, score=9)
        Rating.objects.create(user=self.user2, movie=self.movie, score=10)

        movie = movie_details_queryset().get(tmdb_id=self.movie.tmdb_id)
        serializer = MovieDetailSerializer(movie, context={"tmdb_configuration": {"images": {"secure_base_url": "https://image.tmdb.org/t/p/"}}})
        self.assertEqual(serializer.data["community_rating"], 4.8)
        self.assertEqual(serializer.data["community_rating_count"], 2)


class AvatarAangRemovalTests(TestCase):
    def test_avatar_aang_not_in_database(self):
        self.assertFalse(Movie.objects.filter(tmdb_id=980431).exists())
        self.assertFalse(Movie.objects.filter(title__icontains="Avatar Aang").exists())


class FeaturedMovieQuerySerializerTests(TestCase):
    def test_valid_seed(self):
        from apps.movies.serializers import FeaturedMovieQuerySerializer
        serializer = FeaturedMovieQuerySerializer(data={"seed": "valid_seed_123"})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["seed"], "valid_seed_123")

    def test_blank_seed(self):
        from apps.movies.serializers import FeaturedMovieQuerySerializer
        serializer = FeaturedMovieQuerySerializer(data={"seed": ""})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["seed"], "")

    def test_seed_too_long(self):
        from apps.movies.serializers import FeaturedMovieQuerySerializer
        serializer = FeaturedMovieQuerySerializer(data={"seed": "x" * 129})
        self.assertFalse(serializer.is_valid())
        self.assertIn("seed", serializer.errors)

