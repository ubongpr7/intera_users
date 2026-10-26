from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import PlatformStaffInvitation, User


@override_settings(ADMIN_FRONTEND_SITE_URL="https://admin.dev.interaims.com")
class AdminPortalAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("member@example.com", password="StrongPassword123!")
        self.staff = User.objects.create_user("staff@example.com", password="StrongPassword123!", is_staff=True)
        self.superuser = User.objects.create_superuser("owner@example.com", password="StrongPassword123!")

    def test_non_staff_cannot_access_admin_context(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/accounts/users/admin-me/").status_code, 403)

    def test_staff_can_access_admin_context(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get("/accounts/users/admin-me/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])
        self.assertFalse(response.data["is_superuser"])

    def test_staff_can_read_platform_admin_summary(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get("/accounts/users/admin-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["users"]["total"], 3)
        self.assertEqual(response.data["users"]["staff"], 2)
        self.assertIn("workspaces", response.data)

    def test_platform_user_list_includes_joined_and_last_login_timestamps(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.get("/accounts/users/")
        self.assertEqual(response.status_code, 200)
        users = response.data["results"] if isinstance(response.data, dict) else response.data
        listed = next(user for user in users if user["id"] == self.user.id)
        self.assertIsNotNone(listed["date_joined"])
        self.assertIn("last_login", listed)

    def test_non_staff_cannot_read_platform_admin_summary(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/accounts/users/admin-summary/").status_code, 403)

    def test_staff_can_update_user_referral_code_and_commission(self):
        self.client.force_authenticate(self.staff)

        response = self.client.patch(
            f"/accounts/users/{self.user.pk}/",
            {"referral_code": "UPDATEDCODE", "referral_commission_rate": "0.10000", "is_verified": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.referral_code, "UPDATEDCODE")
        self.assertEqual(str(self.user.referral_commission_rate), "0.10000")
        self.assertTrue(self.user.is_verified)

    @patch("mainapps.accounts.views.send_html_email")
    def test_only_superuser_can_create_platform_staff_invitation(self, send_email):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post("/accounts/platform-staff-invitations/", {"email": "new@example.com"}).status_code, 403)

        self.client.force_authenticate(self.superuser)
        response = self.client.post("/accounts/platform-staff-invitations/", {"email": "new@example.com"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        send_email.assert_called_once()
        self.assertIn("admin.dev.interaims.com/accounts/admin-invite/", send_email.call_args.kwargs["context"]["accept_url"])

    @patch("mainapps.accounts.views.send_html_email")
    def test_invitation_promotes_existing_user_without_superuser(self, _send_email):
        self.client.force_authenticate(self.superuser)
        self.client.post("/accounts/platform-staff-invitations/", {"email": self.user.email})
        invitation = PlatformStaffInvitation.objects.get(email=self.user.email)
        raw_token = _send_email.call_args.kwargs["context"]["accept_url"].rsplit("/", 1)[-1]

        response = self.client.post("/accounts/platform-staff-invitations/accept/", {
            "token": raw_token,
            "first_name": "Platform",
            "last_name": "Staff",
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(invitation.status, PlatformStaffInvitation.Status.ACCEPTED)

        replay = self.client.post("/accounts/platform-staff-invitations/accept/", {"token": raw_token, "first_name": "Again"})
        self.assertEqual(replay.status_code, 400)

    @patch("mainapps.accounts.views.send_html_email")
    def test_invitation_creates_new_staff_user_with_password(self, _send_email):
        self.client.force_authenticate(self.superuser)
        self.client.post("/accounts/platform-staff-invitations/", {"email": "new@example.com"})
        raw_token = _send_email.call_args.kwargs["context"]["accept_url"].rsplit("/", 1)[-1]
        response = self.client.post("/accounts/platform-staff-invitations/accept/", {
            "token": raw_token,
            "first_name": "New",
            "last_name": "Staff",
            "password": "StrongPassword123!",
        })
        self.assertEqual(response.status_code, 200)
        created = User.objects.get(email="new@example.com")
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
