from django.urls import path
from .views import ChangePasswordView, CsrfView, LoginView, LogoutView, MeView, ProfileView, RegisterView, PasswordResetRequestView, PasswordResetConfirmView
from .preferences import PreferencesView, PreferenceOptionsView
from .public import PublicProfileView, PublicReviewsView, PublicWatchlistView

app_name = "users"
urlpatterns = [
    path('profiles/<int:user_id>/', PublicProfileView.as_view(), name='public-profile'),
    path('profiles/<int:user_id>/reviews/', PublicReviewsView.as_view(), name='public-reviews'),
    path('profiles/<int:user_id>/watchlist/', PublicWatchlistView.as_view(), name='public-watchlist'),
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/credentials/", MeView.as_view(), name="credentials"),
    path("me/password/", ChangePasswordView.as_view(), name="password"),
    path("me/profile/", ProfileView.as_view(), name="profile"),
    path("me/preferences/", PreferencesView.as_view(), name="preferences"),
    path("preferences/options/", PreferenceOptionsView.as_view(), name="preference-options"),
]
