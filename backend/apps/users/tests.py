from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import is_main_admin_user
from apps.users.services.profiles import get_or_create_profile

User = get_user_model()


class UserCredentialManagementTests(TestCase):
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

        self.regular_user = User.objects.create_user(
            username="cine_viewer",
            email="viewer@example.com",
            password="ViewerPassword123!",
        )

    def test_main_admin_identified(self):
        self.assertTrue(is_main_admin_user(self.main_admin))
        self.assertFalse(is_main_admin_user(self.regular_user))

    def test_regular_user_update_username_valid(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch("/api/v1/users/me/", {"username": "cine_expert"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.username, "cine_expert")

    def test_regular_user_cannot_claim_reserved_username(self):
        self.client.force_authenticate(user=self.regular_user)
        for reserved in ["admin", "administrator", "root", "system", "superuser"]:
            response = self.client.patch("/api/v1/users/me/", {"username": reserved}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("reserved", str(response.data).lower())

    def test_regular_user_cannot_claim_duplicate_username(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch("/api/v1/users/me/", {"username": "admin"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_regular_user_update_email_typo_rejected(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch("/api/v1/users/me/", {"email": "viewer@gmail.co"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("invalid email domain", str(response.data).lower())

    def test_regular_user_update_email_valid(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch("/api/v1/users/me/", {"email": "viewer.new@gmail.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.email, "viewer.new@gmail.com")

    def test_main_admin_cannot_clear_email(self):
        self.client.force_authenticate(user=self.main_admin)
        response = self.client.patch("/api/v1/users/me/", {"email": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valid email", str(response.data).lower())

    def test_change_password_verification(self):
        self.client.force_authenticate(user=self.regular_user)
        # Wrong current password
        response = self.client.post("/api/v1/users/me/password/", {
            "current_password": "WrongPassword!",
            "new_password": "BrandNewPass888!",
            "confirm_password": "BrandNewPass888!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Mismatch
        response = self.client.post("/api/v1/users/me/password/", {
            "current_password": "ViewerPassword123!",
            "new_password": "BrandNewPass888!",
            "confirm_password": "MismatchPass888!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid
        response = self.client.post("/api/v1/users/me/password/", {
            "current_password": "ViewerPassword123!",
            "new_password": "BrandNewPass888!",
            "confirm_password": "BrandNewPass888!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.regular_user.check_password("BrandNewPass888!"))

    def test_main_admin_retains_privileges_after_username_and_email_change(self):
        self.client.force_authenticate(user=self.main_admin)
        response = self.client.patch("/api/v1/users/me/", {
            "username": "ishan_lead",
            "email": "lead.ishan@example.com",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.main_admin.refresh_from_db()
        self.assertEqual(self.main_admin.username, "ishan_lead")
        self.assertEqual(self.main_admin.email, "lead.ishan@example.com")
        self.assertTrue(is_main_admin_user(self.main_admin))
        self.assertTrue(self.main_admin.profile.is_main_admin)
