from django.urls import path

from .views import GenreListView, MovieDetailView, MovieListView

app_name = "movies"
urlpatterns = [
    path("", MovieListView.as_view(), name="list"),
    path("genres/", GenreListView.as_view(), name="genres"),
    path("<int:tmdb_id>/", MovieDetailView.as_view(), name="detail"),
]
