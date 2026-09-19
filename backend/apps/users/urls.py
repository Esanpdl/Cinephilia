from django.urls import path
from .views import CsrfView, LoginView, LogoutView, MeView, ProfileView, RegisterView

app_name = "users"
urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/profile/", ProfileView.as_view(), name="profile"),
]
