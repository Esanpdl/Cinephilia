from django.contrib.auth import get_user_model, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.movies.models import Genre
from .models import Profile, is_main_admin_user
from .services.profiles import get_or_create_profile
from .validators import (
    RESERVED_USERNAMES,
    validate_custom_email,
    validate_custom_password,
    validate_custom_username,
)

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    favorite_genres = serializers.SlugRelatedField(slug_field="tmdb_id", queryset=Genre.objects.all(), many=True, required=False)

    class Meta:
        model = Profile
        fields = ["display_name", "bio", "is_film_student", "favorite_genres"]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    is_main_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "is_superuser", "is_main_admin", "profile"]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_main_admin(self, obj):
        return is_main_admin_user(obj)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_film_student = serializers.BooleanField(default=False)

    class Meta:
        model = User
        fields = ["username", "email", "password", "display_name", "is_film_student"]
        extra_kwargs = {"email": {"required": False, "allow_blank": True}}

    def validate_username(self, value):
        try:
            value = validate_custom_username(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.messages if hasattr(err, "messages") else str(err))
        if value.lower() in RESERVED_USERNAMES:
            raise serializers.ValidationError("This username is reserved.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is unavailable.")
        return value

    def validate_email(self, value):
        if not value or not value.strip():
            return ""
        try:
            value = validate_custom_email(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.messages if hasattr(err, "messages") else str(err))
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs.get("email", ""))
        try:
            validate_custom_password(attrs["password"])
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages if hasattr(error, "messages") else [str(error)]}) from None
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


class UpdateCredentialsSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30, required=False)
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)

    def validate_username(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Username cannot be empty.")
        user = self.context["request"].user
        try:
            value = validate_custom_username(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.messages if hasattr(err, "messages") else str(err))
        if value.lower() in RESERVED_USERNAMES and not is_main_admin_user(user):
            raise serializers.ValidationError("This username is reserved.")
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        user = self.context["request"].user
        if not value or not value.strip():
            if is_main_admin_user(user):
                raise serializers.ValidationError("Main administrator must have a valid email address.")
            return ""
        try:
            value = validate_custom_email(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.messages if hasattr(err, "messages") else str(err))
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def update(self, instance, validated_data):
        is_main = is_main_admin_user(instance)
        if "username" in validated_data:
            instance.username = validated_data["username"]
        if "email" in validated_data:
            instance.email = validated_data["email"]
        instance.save()
        if is_main:
            profile = get_or_create_profile(instance)
            if not profile.is_main_admin:
                profile.is_main_admin = True
                profile.save(update_fields=["is_main_admin", "updated_at"])
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, required=True, trim_whitespace=False, max_length=128)
    confirm_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=128)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        confirm = attrs.get("confirm_password")
        new_pw = attrs["new_password"]
        if confirm is not None and new_pw != confirm:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})

        user = self.context["request"].user
        try:
            validate_custom_password(new_pw)
            password_validation.validate_password(new_pw, user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": error.messages if hasattr(error, "messages") else [str(error)]}) from None
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        new_pw = self.validated_data["new_password"]
        user.set_password(new_pw)
        user.save()
        request = self.context.get("request")
        if request and hasattr(request, "session"):
            update_session_auth_hash(request, user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField(read_only=True)


class SessionSerializer(CsrfSerializer):
    user = UserSerializer(read_only=True)
