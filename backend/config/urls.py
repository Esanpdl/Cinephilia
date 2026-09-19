from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("admin/", admin.site.urls),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/movies/", include("apps.movies.urls")),
    path("api/v1/ratings/", include("apps.ratings.urls")),
    path("api/v1/recommendations/", include("apps.recommendations.urls")),
    path("api/v1/cinematography/", include("apps.cinematography.urls")),
    path("api/v1/admin-panel/", include("apps.admin_panel.urls")),
]
