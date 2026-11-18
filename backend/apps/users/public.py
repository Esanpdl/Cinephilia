"""Public, explicitly allowlisted cinema profiles. No shared response caching."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import Http404
from rest_framework import serializers
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.movies.serializers import GenreSerializer, MovieSummarySerializer
from apps.movies.services.presentation import MediaContextMixin
from apps.ratings.models import Rating, WatchlistItem
from apps.ratings.serializers import ReviewSerializer, WatchlistSerializer


class PublicProfileSerializer(serializers.Serializer):
    email = serializers.EmailField(read_only=True, required=False)
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField(source='profile.display_name', default='')
    bio = serializers.CharField(source='profile.bio', default='')
    is_film_student = serializers.BooleanField(source='profile.is_film_student', default=False)
    watchlist_public = serializers.BooleanField(source='profile.watchlist_public', default=False)
    favorite_genres = GenreSerializer(source='profile.favorite_genres', many=True, read_only=True)

    def to_representation(self, instance):
        result = super().to_representation(instance)
        profile = getattr(instance, 'profile', None)
        if profile and profile.email_public and instance.email:
            result['email'] = instance.email
        else:
            result.pop('email', None)
        return result


class PublicReviewSerializer(ReviewSerializer):
    movie = MovieSummarySerializer(read_only=True)

    class Meta(ReviewSerializer.Meta):
        fields = ReviewSerializer.Meta.fields + ['movie']


class PublicMixin:
    permission_classes = [AllowAny]
    authentication_classes = []

    def owner(self):
        if not hasattr(self, '_owner'):
            self._owner = get_object_or_404(get_user_model().objects.select_related('profile').prefetch_related('profile__favorite_genres'), pk=self.kwargs['user_id'], is_active=True)
        return self._owner

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class PublicProfileView(PublicMixin, RetrieveAPIView):
    serializer_class = PublicProfileSerializer

    def get_object(self):
        return self.owner()


class PublicReviewsView(PublicMixin, MediaContextMixin, ListAPIView):
    serializer_class = PublicReviewSerializer

    def get_queryset(self):
        return Rating.objects.filter(user=self.owner(), review_hidden=False).exclude(review_text='').select_related('user', 'movie').prefetch_related('movie__genres').order_by('-review_updated_at', '-pk')


class PublicWatchlistView(PublicMixin, MediaContextMixin, ListAPIView):
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        user = self.owner()
        if not getattr(getattr(user, 'profile', None), 'watchlist_public', False):
            raise Http404('This watchlist is private.')
        return WatchlistItem.objects.filter(user=user).select_related('movie').prefetch_related('movie__genres').order_by('-created_at', '-pk')
