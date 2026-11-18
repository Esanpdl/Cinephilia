from django.urls import path

from .views import FeaturedMovieView, GenreListView, MovieDetailView, MovieListView, MovieOptionsView

app_name = "movies"
urlpatterns = [
    path("", MovieListView.as_view(), name="list"),
    path("featured/", FeaturedMovieView.as_view(), name="featured"),
    path("genres/", GenreListView.as_view(), name="genres"),
    path("options/", MovieOptionsView.as_view(), name="options"),
    path("<int:tmdb_id>/", MovieDetailView.as_view(), name="detail"),
]
