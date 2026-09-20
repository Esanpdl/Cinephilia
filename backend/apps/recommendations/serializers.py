from rest_framework import serializers
from apps.movies.serializers import MovieSummarySerializer


class RecommendationQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    exclude_watchlist = serializers.BooleanField(default=True)
    offset = serializers.IntegerField(min_value=0, default=0, required=False)
    refresh_seed = serializers.CharField(max_length=128, required=False, allow_blank=True)



class ComponentSerializer(serializers.Serializer):
    content = serializers.FloatField(allow_null=True)
    collaborative = serializers.FloatField(allow_null=True)
    popularity = serializers.FloatField()


class WeightSerializer(serializers.Serializer):
    content = serializers.FloatField()
    collaborative = serializers.FloatField()
    popularity = serializers.FloatField()


class RecommendationItemSerializer(serializers.Serializer):
    movie = MovieSummarySerializer()
    score = serializers.FloatField()
    components = ComponentSerializer()
    effective_weights = WeightSerializer()


class RecommendationProfileSerializer(serializers.Serializer):
    rated_movies = serializers.IntegerField()
    content_seed_count = serializers.IntegerField()
    collaborative_history_count = serializers.IntegerField()
    collaborative_available = serializers.BooleanField()
    mode = serializers.ChoiceField(choices=["hybrid", "content", "collaborative", "popularity"])


class ModelAvailabilitySerializer(serializers.Serializer):
    content = serializers.BooleanField()
    collaborative = serializers.BooleanField()


class RecommendationSerializer(serializers.Serializer):
    results = RecommendationItemSerializer(many=True)
    profile = RecommendationProfileSerializer()
    models = ModelAvailabilitySerializer()
    configured_weights = WeightSerializer()
    candidate_count = serializers.IntegerField()
