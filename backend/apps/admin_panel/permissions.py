from rest_framework.permissions import BasePermission
from apps.users.models import is_main_admin_user


class IsAdminUser(BasePermission):
    """Allows access only to staff/admin users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsMainAdminUser(BasePermission):
    """Allows access only to the main administrator.
    
    Guards sensitive admin actions (e.g. promoting, demoting, or creating admins).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_main_admin_user(request.user))
