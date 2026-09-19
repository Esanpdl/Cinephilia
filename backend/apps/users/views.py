from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import CsrfSessionAuthentication
from .serializers import CsrfSerializer, LoginSerializer, ProfileSerializer, RegisterSerializer, SessionSerializer, UserSerializer
from .services.profiles import get_or_create_profile


class AuthView(APIView):
    authentication_classes = [CsrfSessionAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class CsrfView(AuthView):
    @extend_schema(responses=CsrfSerializer, description="Sets the CSRF cookie. Send csrf_token in X-CSRFToken with every unsafe request and include session cookies.")
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(AuthView):
    throttle_scope = "register"

    @extend_schema(request=RegisterSerializer, responses={201: SessionSerializer}, description="Create a normal account and sign in. CSRF is required even before login. Email is optional and is not verified.")
    def post(self, request):
        if request.user.is_authenticated:
            raise ValidationError("Log out before registering another account.")
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            raise ValidationError({"username": "This username is unavailable."}) from None
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"user": UserSerializer(user).data, "csrf_token": get_token(request)}, status=status.HTTP_201_CREATED)


class LoginView(AuthView):
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=SessionSerializer, description="Sign in with username/password and a CSRF token. Login rotates the token; use the returned token for later writes.")
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise ValidationError({"detail": "Invalid username or password."})
        get_or_create_profile(user)
        login(request, user)
        return Response({"user": UserSerializer(user).data, "csrf_token": get_token(request)})


class LogoutView(AuthView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return get_or_create_profile(self.request.user)
