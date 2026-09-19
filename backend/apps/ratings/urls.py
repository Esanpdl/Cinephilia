from django.urls import path
from .views import RatingDetailView, RatingListView, WatchlistDetailView, WatchlistListView, MovieReviewListView, OwnedReviewView

app_name = "ratings"
urlpatterns = [
    path("", RatingListView.as_view(), name="list"),
    path("reviews/<int:tmdb_id>/", MovieReviewListView.as_view(), name="movie-reviews"),
    path("reviews/<int:tmdb_id>/mine/", OwnedReviewView.as_view(), name="own-review"),
    path("watchlist/", WatchlistListView.as_view(), name="watchlist"),
    path("watchlist/<int:tmdb_id>/", WatchlistDetailView.as_view(), name="watchlist-detail"),
    path("<int:tmdb_id>/", RatingDetailView.as_view(), name="detail"),
]
