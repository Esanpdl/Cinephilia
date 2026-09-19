from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.movies.models import Genre
from .models import Profile
from .services.profiles import get_or_create_profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    favorite_genres = serializers.SlugRelatedField(slug_field="tmdb_id", queryset=Genre.objects.all(), many=True, required=False)

    class Meta:
        model = Profile
        fields = ["display_name", "bio", "is_film_student", "favorite_genres"]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "profile"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_film_student = serializers.BooleanField(default=False)

    class Meta:
        model = User
        fields = ["username", "email", "password", "display_name", "is_film_student"]
        extra_kwargs = {"email": {"required": False}}

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs.get("email", ""))
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from None
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        display_name = validated_data.pop("display_name", "")
        film_student = validated_data.pop("is_film_student")
        user = User.objects.create_user(**validated_data)
        profile = get_or_create_profile(user)
        profile.display_name, profile.is_film_student = display_name, film_student
        profile.save(update_fields=["display_name", "is_film_student", "updated_at"])
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField(read_only=True)


class SessionSerializer(CsrfSerializer):
    user = UserSerializer(read_only=True)
