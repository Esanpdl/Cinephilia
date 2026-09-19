from rest_framework.authentication import SessionAuthentication
from drf_spectacular.authentication import SessionScheme


class CsrfSessionAuthentication(SessionAuthentication):
    """Also protect anonymous login/registration, where DRF skips CSRF by default."""

    def authenticate(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            self.enforce_csrf(request)
        return super().authenticate(request)


class CsrfSessionScheme(SessionScheme):
    target_class = "apps.users.authentication.CsrfSessionAuthentication"
    priority = 1
