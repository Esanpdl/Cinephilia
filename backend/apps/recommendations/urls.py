from django.urls import path
from .views import RecommendationView
from .selection import FromFilmsView

app_name = "recommendations"
urlpatterns = [path("", RecommendationView.as_view(), name="list"), path('from-films/', FromFilmsView.as_view(), name='from-films')]
