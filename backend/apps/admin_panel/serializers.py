from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.users.models import is_main_admin_user
from apps.users.services.profiles import get_or_create_profile
from apps.users.validators import (
    RESERVED_USERNAMES,
    validate_custom_email,
    validate_custom_password,
    validate_custom_username,
)

User = get_user_model()


class AdminUserListItemSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    is_film_student = serializers.SerializerMethodField()
    is_main_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_staff",
            "is_superuser",
            "is_main_admin",
            "is_active",
            "display_name",
            "is_film_student",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.display_name if profile else ""

    @extend_schema_field(serializers.BooleanField())
    def get_is_film_student(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.is_film_student if profile else False

    @extend_schema_field(serializers.BooleanField())
    def get_is_main_admin(self, obj):
        return is_main_admin_user(obj)


class CreateAdminSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_username(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Username is required.")
        try:
            value = validate_custom_username(value)
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.messages if hasattr(err, "messages") else str(err))
        if value.lower() in RESERVED_USERNAMES:
            raise serializers.ValidationError("This username is reserved.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required.")
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
        password = validated_data.pop("password")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=password,
            is_staff=True,
            is_superuser=False,
        )
        profile = get_or_create_profile(user)
        profile.display_name = display_name
        profile.is_main_admin = False
        profile.save(update_fields=["display_name", "is_main_admin", "updated_at"])
        return user


class AdminStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_admins = serializers.IntegerField()
    total_movies = serializers.IntegerField()
    total_ratings = serializers.IntegerField()
