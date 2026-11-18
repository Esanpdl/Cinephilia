from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from config.api import PageQuerySerializer
from apps.movies.models import Movie
from apps.movies.services.presentation import MediaContextMixin
from .models import Rating, WatchlistItem
from .serializers import RatingSerializer, RatingWriteSerializer, WatchlistSerializer, ReviewSerializer, OwnedReviewSerializer, ReviewWriteSerializer
from .services.reviews import save_rating, remove_rating


@extend_schema(parameters=[PageQuerySerializer])
class OwnedListView(MediaContextMixin, ListAPIView):
    def filter_queryset(self, queryset):
        params = PageQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return super().filter_queryset(queryset)


class RatingListView(OwnedListView):
    serializer_class = RatingSerializer

    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user).select_related("movie").prefetch_related("movie__genres").order_by("-updated_at", "-pk")


@extend_schema_view(
    put=extend_schema(request=RatingWriteSerializer, responses={200: RatingSerializer, 201: RatingSerializer}, description="Create or replace your 1-10 rating using a TMDB movie ID. The session determines the owner."),
    delete=extend_schema(request=None, responses={204: None}),
)
class RatingDetailView(MediaContextMixin, GenericAPIView):
    serializer_class = RatingSerializer

    def get(self, request, tmdb_id):
        rating = get_object_or_404(Rating.objects.select_related("movie").prefetch_related("movie__genres"), user=request.user, movie__tmdb_id=tmdb_id)
        return Response(self.get_serializer(rating).data)

    def put(self, request, tmdb_id):
        incoming = RatingWriteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        movie = get_object_or_404(Movie.objects.prefetch_related("genres"), tmdb_id=tmdb_id)
        rating, created = save_rating(request.user, movie, incoming.validated_data["score"])
        rating.movie = movie
        return Response(self.get_serializer(rating).data, status=201 if created else 200)

    def delete(self, request, tmdb_id):
        movie = get_object_or_404(Movie, tmdb_id=tmdb_id)
        remove_rating(request.user, movie)
        return Response(status=204)


@extend_schema(parameters=[PageQuerySerializer])
class MovieReviewListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        params = PageQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        movie = get_object_or_404(Movie, tmdb_id=self.kwargs["tmdb_id"])
        return Rating.objects.filter(movie=movie, review_hidden=False, user__is_active=True).exclude(review_text="").select_related("user").order_by("-review_updated_at", "-pk")


@extend_schema_view(
    put=extend_schema(request=ReviewWriteSerializer, responses={200: OwnedReviewSerializer, 201: OwnedReviewSerializer}, description="Create or edit your single film review. Stars: 0.5–5 in 0.5 steps. Text: 10–3000 characters, no links or repeated text across films. At most 5 changes/minute and 20/24 hours across all review write routes."),
    delete=extend_schema(request=None, responses={204: None}, description="Remove your written review while retaining your star rating. Counts toward review write limits."),
)
class OwnedReviewView(GenericAPIView):
    serializer_class = OwnedReviewSerializer

    def get(self, request, tmdb_id):
        rating = get_object_or_404(Rating.objects.select_related("user").exclude(review_text=""), user=request.user, movie__tmdb_id=tmdb_id)
        return Response(self.get_serializer(rating).data)

    def put(self, request, tmdb_id):
        incoming = ReviewWriteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        movie = get_object_or_404(Movie, tmdb_id=tmdb_id)
        rating, created = save_rating(request.user, movie, int(incoming.validated_data["stars"] * 2), incoming.validated_data["text"])
        rating.user = request.user
        return Response(self.get_serializer(rating).data, status=201 if created else 200)

    def delete(self, request, tmdb_id):
        movie = get_object_or_404(Movie, tmdb_id=tmdb_id)
        remove_rating(request.user, movie, review_only=True)
        return Response(status=204)


class WatchlistListView(OwnedListView):
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user).select_related("movie").prefetch_related("movie__genres").order_by("-created_at", "-pk")


@extend_schema_view(
    put=extend_schema(request=None, responses={200: WatchlistSerializer, 201: WatchlistSerializer}, description="Idempotently add this TMDB movie to your watchlist; no request body."),
    delete=extend_schema(request=None, responses={204: None}),
)
class WatchlistDetailView(MediaContextMixin, GenericAPIView):
    serializer_class = WatchlistSerializer

    def get(self, request, tmdb_id):
        item = get_object_or_404(WatchlistItem.objects.select_related("movie").prefetch_related("movie__genres"), user=request.user, movie__tmdb_id=tmdb_id)
        return Response(self.get_serializer(item).data)

    def put(self, request, tmdb_id):
        movie = get_object_or_404(Movie.objects.prefetch_related("genres"), tmdb_id=tmdb_id)
        item, created = WatchlistItem.objects.get_or_create(user=request.user, movie=movie)
        return Response(self.get_serializer(item).data, status=201 if created else 200)

    def delete(self, request, tmdb_id):
        movie = get_object_or_404(Movie, tmdb_id=tmdb_id)
        WatchlistItem.objects.filter(user=request.user, movie=movie).delete()
        return Response(status=204)
