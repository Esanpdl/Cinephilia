from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import is_main_admin_user
from apps.users.services.profiles import get_or_create_profile

User = get_user_model()


class AdminDashboardManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.main_admin = User.objects.create_superuser(
            username="admin",
            email="esan3125@gmail.com",
            password="ish@npoudel888",
        )
        profile = get_or_create_profile(self.main_admin)
        profile.is_main_admin = True
        profile.save()

        self.staff_admin = User.objects.create_user(
            username="staff_editor",
            email="staff@example.com",
            password="StaffPassword123!",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular_member",
            email="member@example.com",
            password="MemberPassword123!",
        )

    def test_admin_list_and_stats(self):
        self.client.force_authenticate(user=self.staff_admin)
        response = self.client.get("/api/v1/admin-panel/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 3)

        response = self.client.get("/api/v1/admin-panel/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_users", response.data)
        self.assertIn("total_admins", response.data)

    def test_main_admin_creates_admin(self):
        self.client.force_authenticate(user=self.main_admin)
        response = self.client.post("/api/v1/admin-panel/users/create-admin/", {
            "username": "new_staff_curator",
            "email": "curator@example.com",
            "password": "CuratorPass888!",
            "display_name": "Curator Eva",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_admin = User.objects.get(username="new_staff_curator")
        self.assertTrue(new_admin.is_staff)
        self.assertFalse(new_admin.is_superuser)
        self.assertFalse(is_main_admin_user(new_admin))

    def test_main_admin_promote_and_demote(self):
        self.client.force_authenticate(user=self.main_admin)
        # Promote
        response = self.client.post(f"/api/v1/admin-panel/users/{self.regular_user.id}/promote/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)

        # Demote
        response = self.client.post(f"/api/v1/admin-panel/users/{self.regular_user.id}/demote/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_staff)
        self.assertFalse(self.regular_user.is_superuser)

    def test_main_admin_cannot_be_demoted_or_deleted(self):
        self.client.force_authenticate(user=self.main_admin)
        # Demote attempt
        response = self.client.post(f"/api/v1/admin-panel/users/{self.main_admin.id}/demote/")
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

        # Delete attempt
        response = self.client.delete(f"/api/v1/admin-panel/users/{self.main_admin.id}/delete/")
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_staff_admin_forbidden_from_destructive_actions(self):
        self.client.force_authenticate(user=self.staff_admin)
        # Cannot create admin
        response = self.client.post("/api/v1/admin-panel/users/create-admin/", {
            "username": "unauthorized_admin",
            "email": "unauth@example.com",
            "password": "Password123!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot promote
        response = self.client.post(f"/api/v1/admin-panel/users/{self.regular_user.id}/promote/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot demote
        response = self.client.post(f"/api/v1/admin-panel/users/{self.staff_admin.id}/demote/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot delete
        response = self.client.delete(f"/api/v1/admin-panel/users/{self.regular_user.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
