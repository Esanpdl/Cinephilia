"""REST routes for the admin_panel domain."""
from django.urls import path

from .views import (
    AdminCreateAdminView,
    AdminDeleteUserView,
    AdminDemoteUserView,
    AdminPromoteUserView,
    AdminStatsView,
    AdminSetUserActiveView,
    AdminUserListView,
)

app_name = "admin_panel"
urlpatterns = [
    path("users/", AdminUserListView.as_view(), name="user_list"),
    path("users/create-admin/", AdminCreateAdminView.as_view(), name="create_admin"),
    path("users/<int:user_id>/promote/", AdminPromoteUserView.as_view(), name="promote_user"),
    path("users/<int:user_id>/demote/", AdminDemoteUserView.as_view(), name="demote_user"),
    path("users/<int:user_id>/delete/", AdminDeleteUserView.as_view(), name="delete_user"),
    path("users/<int:user_id>/active/", AdminSetUserActiveView.as_view(), name="set_user_active"),
    path("stats/", AdminStatsView.as_view(), name="stats"),
]
