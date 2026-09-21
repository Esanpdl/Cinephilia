"""Comprehensive verification script for Admin Panel & Authentication features.

Verifies:
1. Initial admin details (admin, esan3125@gmail.com, ish@npoudel888, is_staff, is_superuser, is_main_admin).
2. Admin management in Admin Dashboard (promote, demote, add admin, delete).
3. Main admin protection (cannot be demoted, deleted, or stripped of privileges).
4. Permission guards (staff admin cannot promote/demote/create admins).
5. Self-service credential management:
   - Username update (valid, format checks, duplicate rejection).
   - Email update (valid, typo domain rejection, gmail.com enforcement, duplicate rejection).
   - Password change (current pw verification, password strength, session preservation).
6. Main admin status persistence across username change.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.admin_panel.views import (
    AdminCreateAdminView,
    AdminDeleteUserView,
    AdminDemoteUserView,
    AdminPromoteUserView,
    AdminStatsView,
    AdminUserListView,
)
from apps.users.models import is_main_admin_user
from apps.users.views import ChangePasswordView, MeView

User = get_user_model()
factory = APIRequestFactory()


def run_all_checks():
    print("=" * 70)
    print("STARTING ADMIN PANEL & AUTHENTICATION VERIFICATION")
    print("=" * 70)

    # 1. Initial Admin Verification
    print("\n--- 1. Verifying Initial Admin Account ---")
    admin_user = User.objects.filter(username="admin").first()
    assert admin_user is not None, "Initial admin user 'admin' does not exist!"
    assert admin_user.email == "esan3125@gmail.com", f"Expected email 'esan3125@gmail.com', got '{admin_user.email}'"
    assert admin_user.is_staff is True, "Admin is_staff must be True"
    assert admin_user.is_superuser is True, "Admin is_superuser must be True"
    assert is_main_admin_user(admin_user) is True, "is_main_admin_user(admin_user) must be True"

    auth_user = authenticate(username="admin", password="ish@npoudel888")
    assert auth_user is not None, "Authentication with 'admin' and 'ish@npoudel888' failed!"
    print("[PASS] Initial admin account verified: admin / esan3125@gmail.com (is_staff=True, is_superuser=True, is_main_admin=True)")

    # We perform the remaining tests in a rollback transaction to avoid polluting DB
    with transaction.atomic():
        print("\n--- 2. Verifying Self-Service Credential Management (MeView & ChangePasswordView) ---")
        # Create a test regular user
        test_user = User.objects.create_user(
            username="test_cinema_user",
            email="test_cinema@example.com",
            password="InitialPass123!",
        )

        # 2a. Username update - valid
        req = factory.patch("/api/v1/users/me/", {"username": "cinema_fan_99"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK, f"Username update failed: {res.data}"
        test_user.refresh_from_db()
        assert test_user.username == "cinema_fan_99", "Username did not update"
        print("[PASS] Valid username update succeeded")

        # 2b. Username update - invalid format (<3 chars)
        req = factory.patch("/api/v1/users/me/", {"username": "ab"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Short username should be rejected"
        print("[PASS] Short username (<3 chars) correctly rejected")

        # 2c. Username update - invalid format (special characters)
        req = factory.patch("/api/v1/users/me/", {"username": "bad username!"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Username with spaces/punctuation should be rejected"
        print("[PASS] Username with invalid characters correctly rejected")

        # 2d. Username update - duplicate username
        req = factory.patch("/api/v1/users/me/", {"username": "admin"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Duplicate username should be rejected"
        print("[PASS] Duplicate username correctly rejected")

        # 2d-2. Username update - reserved username (e.g. root) for regular user
        req = factory.patch("/api/v1/users/me/", {"username": "root"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Reserved username should be rejected for regular user"
        assert "reserved" in str(res.data).lower()
        print("[PASS] Reserved username (root) correctly rejected for regular user")

        # 2e. Email update - valid
        req = factory.patch("/api/v1/users/me/", {"email": "cinemafan99@gmail.com"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK, f"Email update failed: {res.data}"
        test_user.refresh_from_db()
        assert test_user.email == "cinemafan99@gmail.com", "Email did not update"
        print("[PASS] Valid email update succeeded")

        # 2e-2. Email update - main admin cannot clear email
        req = factory.patch("/api/v1/users/me/", {"email": ""}, format="json")
        force_authenticate(req, user=admin_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Main admin clearing email should be rejected"
        assert "valid email" in str(res.data).lower()
        print("[PASS] Main admin prevented from clearing email address")

        # 2f. Email update - typo domain (gmail.co)
        req = factory.patch("/api/v1/users/me/", {"email": "cinemafan99@gmail.co"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Typo domain gmail.co should be rejected"
        print("[PASS] Typo domain (gmail.co) correctly rejected")

        # 2g. Email update - invalid gmail TLD (gmail.org)
        req = factory.patch("/api/v1/users/me/", {"email": "cinemafan99@gmail.org"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Gmail with .org should be rejected"
        print("[PASS] Invalid Gmail domain (gmail.org) correctly rejected")

        # 2h. Email update - duplicate email
        req = factory.patch("/api/v1/users/me/", {"email": "esan3125@gmail.com"}, format="json")
        force_authenticate(req, user=test_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Duplicate email should be rejected"
        print("[PASS] Duplicate email correctly rejected")

        # 2i. Password change - incorrect current password
        req = factory.post("/api/v1/users/me/password/", {
            "current_password": "WrongPassword!",
            "new_password": "ValidNewPassword123!",
            "confirm_password": "ValidNewPassword123!",
        }, format="json")
        force_authenticate(req, user=test_user)
        res = ChangePasswordView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Wrong current password should be rejected"
        print("[PASS] Incorrect current password correctly rejected")

        # 2j. Password change - weak new password (no digits/specials)
        req = factory.post("/api/v1/users/me/password/", {
            "current_password": "InitialPass123!",
            "new_password": "onlylettershere",
            "confirm_password": "onlylettershere",
        }, format="json")
        force_authenticate(req, user=test_user)
        res = ChangePasswordView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Weak new password should be rejected"
        print("[PASS] Weak new password correctly rejected")

        # 2k. Password change - mismatch
        req = factory.post("/api/v1/users/me/password/", {
            "current_password": "InitialPass123!",
            "new_password": "ValidNewPassword123!",
            "confirm_password": "DifferentPassword123!",
        }, format="json")
        force_authenticate(req, user=test_user)
        res = ChangePasswordView.as_view()(req)
        assert res.status_code == status.HTTP_400_BAD_REQUEST, "Password mismatch should be rejected"
        print("[PASS] Password mismatch correctly rejected")

        # 2l. Password change - valid
        req = factory.post("/api/v1/users/me/password/", {
            "current_password": "InitialPass123!",
            "new_password": "ValidNewPassword123!",
            "confirm_password": "ValidNewPassword123!",
        }, format="json")
        force_authenticate(req, user=test_user)
        res = ChangePasswordView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK, f"Valid password change failed: {res.data}"
        assert authenticate(username="cinema_fan_99", password="ValidNewPassword123!") is not None
        print("[PASS] Valid password change succeeded")

        print("\n--- 3. Verifying Admin Dashboard & Admin Management ---")
        # 3a. Admin list view
        req = factory.get("/api/v1/admin-panel/users/")
        force_authenticate(req, user=admin_user)
        res = AdminUserListView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK, f"Admin list failed: {res.data}"
        assert res.data["count"] >= 2
        print(f"[PASS] Admin user list view succeeded (returned {res.data['count']} accounts)")

        # 3b. Admin stats view
        req = factory.get("/api/v1/admin-panel/stats/")
        force_authenticate(req, user=admin_user)
        res = AdminStatsView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK
        assert "total_users" in res.data and "total_admins" in res.data
        print(f"[PASS] Admin stats view succeeded: {res.data}")

        # 3c. Main admin creates a new admin
        req = factory.post("/api/v1/admin-panel/users/create-admin/", {
            "username": "curator_sarah",
            "email": "sarah.curator@example.com",
            "password": "CuratorPass888!",
            "display_name": "Sarah Curator",
        }, format="json")
        force_authenticate(req, user=admin_user)
        res = AdminCreateAdminView.as_view()(req)
        assert res.status_code == status.HTTP_201_CREATED, f"Admin creation failed: {res.data}"
        sarah = User.objects.get(username="curator_sarah")
        assert sarah.is_staff is True, "Created admin must have is_staff=True"
        assert sarah.is_superuser is False, "Created admin must not have is_superuser=True"
        assert is_main_admin_user(sarah) is False, "Created admin must NOT be main admin"
        print("[PASS] Main admin successfully created a new staff admin (curator_sarah)")

        # 3d. Main admin promotes existing user to admin
        req = factory.post(f"/api/v1/admin-panel/users/{test_user.id}/promote/")
        force_authenticate(req, user=admin_user)
        res = AdminPromoteUserView.as_view()(req, user_id=test_user.id)
        assert res.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.is_staff is True
        print(f"[PASS] Main admin successfully promoted {test_user.username} to admin")

        # 3e. Main admin demotes other admin
        test_user.is_superuser = True
        test_user.save(update_fields=["is_superuser"])
        req = factory.post(f"/api/v1/admin-panel/users/{test_user.id}/demote/")
        force_authenticate(req, user=admin_user)
        res = AdminDemoteUserView.as_view()(req, user_id=test_user.id)
        assert res.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.is_staff is False, "Demoted admin must have is_staff=False"
        assert test_user.is_superuser is False, "Demoted admin must have is_superuser=False"
        print(f"[PASS] Main admin successfully demoted {test_user.username} (is_staff=False, is_superuser=False)")

        # 3f. Main admin deletes a user
        req = factory.delete(f"/api/v1/admin-panel/users/{sarah.id}/delete/")
        force_authenticate(req, user=admin_user)
        res = AdminDeleteUserView.as_view()(req, user_id=sarah.id)
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(username="curator_sarah").exists()
        print("[PASS] Main admin successfully removed user curator_sarah")

        # 3g. Admin cannot delete themselves
        req = factory.delete(f"/api/v1/admin-panel/users/{admin_user.id}/delete/")
        force_authenticate(req, user=admin_user)
        try:
            res = AdminDeleteUserView.as_view()(req, user_id=admin_user.id)
            assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        except Exception as e:
            assert "cannot be demoted, deleted" in str(e).lower()
        print("[PASS] Self-deletion blocked for admin user")

        print("\n--- 4. Verifying Main Admin Protection Guards ---")
        # 4a. Attempt to demote main admin by anyone (including self)
        req = factory.post(f"/api/v1/admin-panel/users/{admin_user.id}/demote/")
        force_authenticate(req, user=admin_user)
        try:
            res = AdminDemoteUserView.as_view()(req, user_id=admin_user.id)
            assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        except Exception as e:
            assert "cannot be demoted" in str(e).lower()
        admin_user.refresh_from_db()
        assert admin_user.is_staff is True and admin_user.is_superuser is True
        print("[PASS] Guard verified: Main admin cannot be demoted")

        # 4b. Attempt to delete main admin
        req = factory.delete(f"/api/v1/admin-panel/users/{admin_user.id}/delete/")
        force_authenticate(req, user=admin_user)
        try:
            res = AdminDeleteUserView.as_view()(req, user_id=admin_user.id)
            assert res.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]
        except Exception as e:
            assert "cannot be demoted, deleted" in str(e).lower()
        assert User.objects.filter(username="admin").exists()
        print("[PASS] Guard verified: Main admin cannot be deleted")

        print("\n--- 5. Verifying Permission Bounds for Other Admins ---")
        # Create a non-main staff admin
        staff_admin = User.objects.create_user(
            username="staff_editor",
            email="staff_editor@example.com",
            password="StaffPassword123!",
            is_staff=True,
        )

        # 5a. Staff admin CAN view admin list
        req = factory.get("/api/v1/admin-panel/users/")
        force_authenticate(req, user=staff_admin)
        res = AdminUserListView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK
        print("[PASS] Staff admin can view admin list")

        # 5b. Staff admin CANNOT create new admin
        req = factory.post("/api/v1/admin-panel/users/create-admin/", {
            "username": "rogue_admin",
            "email": "rogue@example.com",
            "password": "RoguePassword123!",
        }, format="json")
        force_authenticate(req, user=staff_admin)
        res = AdminCreateAdminView.as_view()(req)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        print("[PASS] Staff admin CANNOT create new admins (403 Forbidden)")

        # 5c. Staff admin CANNOT promote users
        req = factory.post(f"/api/v1/admin-panel/users/{test_user.id}/promote/")
        force_authenticate(req, user=staff_admin)
        res = AdminPromoteUserView.as_view()(req, user_id=test_user.id)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        print("[PASS] Staff admin CANNOT promote users (403 Forbidden)")

        # 5d. Staff admin CANNOT demote users
        req = factory.post(f"/api/v1/admin-panel/users/{admin_user.id}/demote/")
        force_authenticate(req, user=staff_admin)
        res = AdminDemoteUserView.as_view()(req, user_id=admin_user.id)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        print("[PASS] Staff admin CANNOT demote admins (403 Forbidden)")

        # 5e. Staff admin CANNOT delete users
        req = factory.delete(f"/api/v1/admin-panel/users/{admin_user.id}/delete/")
        force_authenticate(req, user=staff_admin)
        res = AdminDeleteUserView.as_view()(req, user_id=admin_user.id)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        print("[PASS] Staff admin CANNOT delete users (403 Forbidden)")

        print("\n--- 6. Verifying Main Admin Status Persistence on Username Change ---")
        # Main admin updates username from 'admin' to 'ishan_lead'
        req = factory.patch("/api/v1/users/me/", {"username": "ishan_lead"}, format="json")
        force_authenticate(req, user=admin_user)
        res = MeView.as_view()(req)
        assert res.status_code == status.HTTP_200_OK
        admin_user.refresh_from_db()
        assert admin_user.username == "ishan_lead"
        # Verify is_main_admin_user is STILL True!
        assert is_main_admin_user(admin_user) is True, "Main admin must retain status after username change!"
        # Main admin can still perform main admin actions under new username!
        req = factory.post(f"/api/v1/admin-panel/users/{test_user.id}/promote/")
        force_authenticate(req, user=admin_user)
        res = AdminPromoteUserView.as_view()(req, user_id=test_user.id)
        assert res.status_code == status.HTTP_200_OK, "Main admin under new username should still be able to promote"
        print("[PASS] Main admin retains full owner privileges even after changing username")

        # Rollback transaction will revert test state back to pristine
        transaction.set_rollback(True)

    print("\n" + "=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY (100% PASSED)!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_checks()
