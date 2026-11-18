from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.movies.models import Movie
from apps.ratings.models import Rating
from apps.users.models import is_main_admin_user
from config.api import CatalogPagination

from .permissions import IsAdminUser, IsMainAdminUser
from .serializers import (
    AdminStatsSerializer,
    AdminUserListItemSerializer,
    CreateAdminSerializer,
)

User = get_user_model()


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    pagination_class = CatalogPagination
    serializer_class = AdminUserListItemSerializer

    def get_queryset(self):
        queryset = User.objects.all().select_related("profile").order_by("-date_joined")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(profile__display_name__icontains=search)
            )
        role = self.request.query_params.get("role", "").strip().lower()
        if role == "admin":
            queryset = queryset.filter(is_staff=True)
        elif role == "user":
            queryset = queryset.filter(is_staff=False)
        return queryset


class AdminCreateAdminView(generics.CreateAPIView):
    permission_classes = [IsMainAdminUser]
    serializer_class = CreateAdminSerializer

    @extend_schema(responses={201: AdminUserListItemSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserListItemSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminPromoteUserView(APIView):
    permission_classes = [IsMainAdminUser]

    @extend_schema(request=None, responses={200: AdminUserListItemSerializer})
    def post(self, request, user_id):
        target_user = get_object_or_404(User, pk=user_id)
        target_user.is_staff = True
        target_user.save(update_fields=["is_staff"])
        return Response(AdminUserListItemSerializer(target_user).data)


class AdminDemoteUserView(APIView):
    permission_classes = [IsMainAdminUser]

    @extend_schema(request=None, responses={200: AdminUserListItemSerializer})
    def post(self, request, user_id):
        target_user = get_object_or_404(User, pk=user_id)
        if is_main_admin_user(target_user):
            raise ValidationError("The main admin cannot be demoted, deleted, or stripped of admin privileges.")
        target_user.is_staff = False
        target_user.is_superuser = False
        target_user.save(update_fields=["is_staff", "is_superuser"])
        return Response(AdminUserListItemSerializer(target_user).data)


class AdminDeleteUserView(APIView):
    permission_classes = [IsMainAdminUser]

    @extend_schema(responses={204: None})
    def delete(self, request, user_id):
        target_user = get_object_or_404(User, pk=user_id)
        if target_user.id == request.user.id or is_main_admin_user(target_user):
            raise ValidationError("The main admin cannot be demoted, deleted, or stripped of admin privileges.")
        target_user.is_active = False
        target_user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminSetUserActiveView(APIView):
    permission_classes = [IsMainAdminUser]

    class Input(serializers.Serializer):
        is_active = serializers.BooleanField()

    @extend_schema(request=Input, responses={200: AdminUserListItemSerializer})
    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        if target.id == request.user.id or is_main_admin_user(target):
            raise ValidationError("The main administrator's account status cannot be changed here.")
        serializer = self.Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        target.is_active = serializer.validated_data['is_active']
        target.save(update_fields=['is_active'])
        return Response(AdminUserListItemSerializer(target).data)


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=AdminStatsSerializer)
    def get(self, request):
        total_users = User.objects.count()
        total_admins = User.objects.filter(is_staff=True).count()
        total_movies = Movie.objects.count()
        total_ratings = Rating.objects.count()
        return Response({
            "total_users": total_users,
            "total_admins": total_admins,
            "total_movies": total_movies,
            "total_ratings": total_ratings,
        })
