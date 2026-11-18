from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from django.contrib.auth import get_user_model
import hashlib
import time
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, BaseThrottle
from rest_framework.views import APIView

from .authentication import CsrfSessionAuthentication
from .serializers import (
    ChangePasswordSerializer,
    CsrfSerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    SessionSerializer,
    UpdateCredentialsSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .services.profiles import get_or_create_profile


class AuthView(APIView):
    authentication_classes = [CsrfSessionAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class RegistrationThrottle(BaseThrottle):
    """Limit successful signups separately from correctable invalid form attempts."""
    success_limit = 5
    failure_limit = 30
    window = 3600

    def allow_request(self, request, view):
        ident = hashlib.sha256(self.get_ident(request).encode()).hexdigest()[:32]
        self.success_key = f'auth:register:success:{ident}'
        self.failure_key = f'auth:register:failure:{ident}'
        self.now = time.time()
        self.successes = [t for t in cache.get(self.success_key, []) if self.now - t < self.window]
        self.failures = [t for t in cache.get(self.failure_key, []) if self.now - t < self.window]
        exceeded = len(self.successes) >= self.success_limit or len(self.failures) >= self.failure_limit
        self.retry_after = max(1, int(self.window - (self.now - min(self.successes if len(self.successes) >= self.success_limit else self.failures)))) if exceeded else 0
        return not exceeded

    def wait(self):
        return self.retry_after

    def record_failure(self):
        self._record(self.failure_key, self.failures, self.now)

    def record_success(self):
        self._record(self.success_key, self.successes, self.now)

    def _record(self, key, history, value):
        history.append(value)
        cache.set(key, history, self.window)


class CsrfView(AuthView):
    @extend_schema(responses=CsrfSerializer, description="Sets the CSRF cookie. Send csrf_token in X-CSRFToken with every unsafe request and include session cookies.")
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(AuthView):
    throttle_classes = []

    def check_throttles(self, request):
        throttle = RegistrationThrottle()
        if not throttle.allow_request(request, self):
            self.throttled(request, throttle.wait())
        self.registration_throttle = throttle

    @extend_schema(request=RegisterSerializer, responses={201: SessionSerializer}, description="Create a normal account and sign in. CSRF is required even before login. Email is optional and is not verified.")
    def post(self, request):
        if request.user.is_authenticated:
            raise ValidationError("Log out before registering another account.")
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            self.registration_throttle.record_failure()
            raise
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            self.registration_throttle.record_failure()
            raise ValidationError({"username": "This username is unavailable."}) from None
        self.registration_throttle.record_success()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"user": UserSerializer(user).data, "csrf_token": get_token(request)}, status=status.HTTP_201_CREATED)


class LoginView(AuthView):
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=SessionSerializer, description="Sign in with username or a unique email address and a password. A CSRF token is required; login rotates it, so use the returned token for later writes.")
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise ValidationError({"detail": "Invalid username or password."})
        get_or_create_profile(user)
        login(request, user)
        return Response({"user": UserSerializer(user).data, "csrf_token": get_token(request)})


class PasswordResetRequestView(AuthView):
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        User = get_user_model()
        matches = list(User.objects.filter(email__iexact=email, is_active=True).exclude(password='').only('id', 'email', 'password', 'username', 'last_login')[:2])
        # Legacy data may contain duplicate emails. Never send reset links to multiple
        # accounts for one address; users can still sign in with their username.
        for user in matches[:1] if len(matches) == 1 else []:
            if not user.has_usable_password():
                continue
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            url = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"
            try:
                send_mail('Reset your Cinephilia password',
                          f"Use this link to choose a new password. It expires after use:\n\n{url}\n\nIf you did not request this, you can ignore this email.",
                          settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Password reset email delivery failed.')
        return Response({'detail': 'If an active account uses that email, password reset instructions have been sent.'})


class PasswordResetConfirmView(AuthView):
    throttle_scope = 'password_reset_confirm'

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        User = get_user_model()
        from django.utils.http import urlsafe_base64_decode
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = User.objects.get(pk=uid, is_active=True)
        except (ValueError, TypeError, User.DoesNotExist):
            raise ValidationError({'token': 'This password reset link is invalid or has expired.'}) from None
        if not default_token_generator.check_token(user, data['token']):
            raise ValidationError({'token': 'This password reset link is invalid or has expired.'})
        try:
            password_validation.validate_password(data['password'], user)
        except DjangoValidationError as error:
            raise ValidationError({'password': error.messages}) from None
        user.set_password(data['password'])
        user.save(update_fields=['password'])
        return Response({'detail': 'Your password has been changed.'})


class LogoutView(AuthView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        user = self.request.user
        if user and user.is_authenticated:
            get_or_create_profile(user)
        return user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UpdateCredentialsSerializer
        return UserSerializer

    @extend_schema(request=UpdateCredentialsSerializer, responses={200: UserSerializer}, description="Update username or email credentials.")
    def patch(self, request, *args, **kwargs):
        serializer = UpdateCredentialsSerializer(request.user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user, context={"request": request}).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: SessionSerializer}, description="Change current user's password with current password verification.")
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "detail": "Password updated successfully.",
            "user": UserSerializer(user, context={"request": request}).data,
            "csrf_token": get_token(request),
        })


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return get_or_create_profile(self.request.user)
