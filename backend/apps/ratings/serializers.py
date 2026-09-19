from rest_framework import serializers
from decimal import Decimal
from apps.movies.serializers import MovieSummarySerializer
from .models import Rating, WatchlistItem
from .services.reviews import validate_review_text


class RatingWriteSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=10)


class RatingSerializer(serializers.ModelSerializer):
    movie = MovieSummarySerializer(read_only=True)
    stars = serializers.SerializerMethodField()

    def get_stars(self, obj) -> float:
        return obj.score / 2

    class Meta:
        model = Rating
        fields = ["movie", "score", "stars", "created_at", "updated_at"]
        read_only_fields = fields


class ReviewWriteSerializer(serializers.Serializer):
    stars = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=Decimal("0.5"), max_value=Decimal("5"))
    text = serializers.CharField(min_length=10, max_length=3000)

    def validate_stars(self, value):
        if value * 2 != (value * 2).to_integral_value():
            raise serializers.ValidationError("Choose 0.5–5 stars in half-star steps.")
        return value

    def validate_text(self, value):
        return validate_review_text(value)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - {"stars", "text"}:
            raise serializers.ValidationError({"non_field_errors": ["Only stars and text may be submitted."]})
        return super().to_internal_value(data)


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="user.username", read_only=True)
    stars = serializers.SerializerMethodField()
    text = serializers.CharField(source="review_text", read_only=True)
    updated_at = serializers.DateTimeField(source="review_updated_at", read_only=True)

    def get_stars(self, obj) -> float:
        return obj.score / 2

    class Meta:
        model = Rating
        fields = ["id", "author", "stars", "text", "updated_at"]
        read_only_fields = fields


class OwnedReviewSerializer(ReviewSerializer):
    class Meta(ReviewSerializer.Meta):
        fields = ReviewSerializer.Meta.fields + ["review_hidden"]
        read_only_fields = fields


class WatchlistSerializer(serializers.ModelSerializer):
    movie = MovieSummarySerializer(read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ["movie", "created_at"]
        read_only_fields = fields
