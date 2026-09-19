from django.urls import path
from . import views
app_name = "cinematography"
urlpatterns = [
    path('films/', views.StudentFilmsView.as_view()),
    path('films/<int:tmdb_id>/', views.StudentFilmView.as_view()),
    path('films/<int:tmdb_id>/similar/', views.SimilarView.as_view()),
    path('films/<int:tmdb_id>/tags/', views.PublicTagsView.as_view()),
    path('techniques/', views.TaxonomyView.as_view()),
    path('cards/', views.CardsView.as_view()),
    path('compare/', views.CompareView.as_view()),
    path('overview/', views.OverviewView.as_view()),
    path('spotlight/', views.SpotlightView.as_view()),
    path('quiz/', views.QuizView.as_view()),
    path('tags/', views.TagsView.as_view()),
    path('moderation/', views.ModerationQueueView.as_view()),
    path('moderation/<int:pk>/', views.ModerateTagView.as_view()),
    path('frames/<int:tmdb_id>/<str:digest>/<str:filename>', views.FrameView.as_view()),
]
