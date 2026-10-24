from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import VerificationCode


class MfaResetFlowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="mfa-reset@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=self.user)

    @patch("mainapps.accounts.views.send_html_email")
    def test_mfa_reset_request_sends_email_code(self, send_email):
        response = self.client.post("/accounts/mfa/reset/request/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertTrue(VerificationCode.objects.filter(user=self.user).exists())
        send_email.assert_called_once()

    def test_mfa_reset_confirm_clears_existing_mfa(self):
        self.user.mfa_secret = "BASE32SECRET"
        self.user.mfa_enabled = True
        self.user.has_setup_mfa = True
        self.user.save(update_fields=["mfa_secret", "mfa_enabled", "has_setup_mfa"])

        VerificationCode.objects.update_or_create(
            user=self.user,
            defaults={
                "code": "123456",
                "expires_at": timezone.now() + timedelta(minutes=10),
                "total_attempts": 0,
                "successful_attempts": 0,
                "slug": self.user.email,
            },
        )

        response = self.client.post("/accounts/mfa/reset/confirm/", {"code": "123456"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.mfa_secret)
        self.assertFalse(self.user.mfa_enabled)
        self.assertFalse(self.user.has_setup_mfa)

    def test_enabled_mfa_cannot_bypass_recovery_with_forced_setup(self):
        self.user.mfa_secret = "BASE32SECRET"
        self.user.mfa_enabled = True
        self.user.has_setup_mfa = True
        self.user.save(update_fields=["mfa_secret", "mfa_enabled", "has_setup_mfa"])

        response = self.client.post("/accounts/mfa/setup/", {"force": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "MFA is already enabled for this account.")
