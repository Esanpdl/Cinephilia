"""Environment-driven settings for the separate Django REST backend."""
from pathlib import Path
import sys

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in backend/.env.")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "apps.users.apps.UsersConfig",
    "apps.movies.apps.MoviesConfig",
    "apps.ratings.apps.RatingsConfig",
    "apps.recommendations.apps.RecommendationsConfig",
    "apps.cinematography.apps.CinematographyConfig",
    "apps.admin_panel.apps.AdminPanelConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.PrivateAPIResponses",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
# Templates serve Django admin and the developer API documentation only.
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if not env("DATABASE_URL", default=""):
    raise ImproperlyConfigured(
        "Set DATABASE_URL in backend/.env to your Supabase PostgreSQL connection URI."
    )
DATABASES = {"default": env.db("DATABASE_URL")}
database = DATABASES["default"]
if database["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL.")
if str(database.get("PORT")) == "6543":
    raise ImproperlyConfigured("Use the Supabase session pooler (5432) or direct connection.")
ssl_mode = env("DATABASE_SSL_MODE", default="require")
if ssl_mode not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("DATABASE_SSL_MODE must require TLS.")
database.setdefault("OPTIONS", {}).update({
    "sslmode": ssl_mode,
    "connect_timeout": 10,
    # Keep Django auth/session tables outside Supabase's default public Data API.
    "options": "-c search_path=public" if "test" in sys.argv[1:] else "-c search_path=cinephilia",
})
# A bounded psycopg pool reuses connections across runserver request threads.
# CONN_MAX_AGE=0 returns the connection to the pool after every request.
database["CONN_MAX_AGE"] = 0
if env.bool('DATABASE_POOL_ENABLED', default=True) and 'test' not in sys.argv[1:]:
    database['OPTIONS']['pool'] = {'min_size': 0, 'max_size': env.int('DATABASE_POOL_MAX_SIZE', default=4),
                                   'max_idle': 60, 'max_lifetime': 600, 'timeout': 20}
database["CONN_HEALTH_CHECKS"] = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.users.authentication.CsrfSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "config.api.CatalogPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "register": "5/hour", "password_reset": "5/hour", "password_reset_confirm": "10/hour"},
    "PAGE_SIZE": 20,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Cinephilia Core API",
    "DESCRIPTION": "Session-authenticated API. First GET /api/v1/users/csrf/, then send X-CSRFToken on writes. Swagger adds the CSRF cookie automatically. Use returned tokens after login/register rotation. All movie IDs are TMDB IDs. User-owned data is private.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Read the current cookie for every write because login rotates CSRF.
    "SWAGGER_UI_SETTINGS": """{
        deepLinking: true,
        displayRequestDuration: true,
        requestInterceptor: function(request) {
            const target = new URL(request.url, window.location.href);
            if (target.origin === window.location.origin) {
                request.credentials = "same-origin";
                if (!["GET", "HEAD", "OPTIONS"].includes((request.method || "GET").toUpperCase())) {
                    const cookie = document.cookie.split("; ").find(value => value.startsWith("csrftoken="));
                    if (cookie) request.headers["X-CSRFToken"] = decodeURIComponent(cookie.slice("csrftoken=".length));
                }
            }
            return request;
        }
    }""",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "TrailerAnalysisStatusEnum": [
            ("ready", "Available"), ("review", "Needs source review"),
            ("missing", "Trailer unavailable"), ("failed", "Analysis failed"),
        ],
    },
}
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Asia/Kathmandu")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TMDB_READ_ACCESS_TOKEN = env("TMDB_READ_ACCESS_TOKEN", default="")
TMDB_API_KEY = env("TMDB_API_KEY", default="")
TMDB_LANGUAGE = env("TMDB_LANGUAGE", default="en-US")
TMDB_MIN_VOTES = env.int("TMDB_MIN_VOTES", default=200)
TMDB_MIN_RATING = env.float("TMDB_MIN_RATING", default=0)
TMDB_CACHE_TTL = env.int("TMDB_CACHE_TTL", default=86400)
TMDB_REQUESTS_PER_SECOND = env.float("TMDB_REQUESTS_PER_SECOND", default=8)
TMDB_DATA_DIR = BASE_DIR.parent / "data" / "tmdb"
CONTENT_INDEX_POINTER = BASE_DIR.parent / "data" / "content" / "current.json"
CONTENT_SERVICE_CLASS = env(
    "CONTENT_SERVICE_CLASS",
    default="apps.recommendations.services.content.engine.TfidfContentService",
)
COLLABORATIVE_MODEL_POINTER = BASE_DIR.parent / "data" / "collaborative" / "current.json"
COLLABORATIVE_SERVICE_CLASS = env(
    "COLLABORATIVE_SERVICE_CLASS",
    default="apps.recommendations.services.collaborative.engine.SVDService",
)

HYBRID_WEIGHTS = {"content": env.float("HYBRID_CONTENT_WEIGHT", default=0.45), "collaborative": env.float("HYBRID_COLLABORATIVE_WEIGHT", default=0.40), "popularity": env.float("HYBRID_POPULARITY_WEIGHT", default=0.15)}
HYBRID_MIN_LIKED_RATING = env.int("HYBRID_MIN_LIKED_RATING", default=7)
HYBRID_MAX_CONTENT_SEEDS = env.int("HYBRID_MAX_CONTENT_SEEDS", default=20)
HYBRID_CATALOG_CACHE_SECONDS = env.int("HYBRID_CATALOG_CACHE_SECONDS", default=86400)
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://127.0.0.1:5173").rstrip("/")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Cinephilia <noreply@cinephilia.local>")
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
