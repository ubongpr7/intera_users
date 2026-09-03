from types import SimpleNamespace

import jwt
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from django.conf import settings
from mainapps.accounts.authorization_context import DEVICE_ENROLLMENT_PROOF_TOKEN_TYPE, _audience
from mainapps.accounts.models import User
from mainapps.permit.models import PlatformChoices
from mainapps.profile.models import CompanyProfile, TrustedWorkspaceDevice


class TrustedWorkspaceDeviceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_superuser(
            email="trusted-device-owner@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.owner,
            name="Trusted Device Workspace",
        )
        self.auth_payload = {
            "profile_id": self.profile.id,
            "platform": PlatformChoices.HOSPERATOR,
            "owner_id": self.owner.id,
        }
        self.client.force_authenticate(
            user=self.owner,
            token=SimpleNamespace(payload=self.auth_payload),
        )

    def test_current_returns_proof_only_for_the_bound_device(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            platform=PlatformChoices.HOSPERATOR,
            device_identifier="android-test-device",
            device_label="Ward phone",
            capabilities=["staff_call"],
            created_by=self.owner,
        )

        response = self.client.get(
            reverse("trusted-workspace-device-current"),
            HTTP_X_DEVICE_ID=device.device_identifier,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_enrolled"])
        self.assertEqual(payload["binding"]["device_identifier"], device.device_identifier)
        proof = payload["binding"]["signed_enrollment_proof"]
        self.assertIsNotNone(proof)
        claims = jwt.decode(
            proof,
            settings.SIMPLE_JWT.get("VERIFYING_KEY") or settings.SECRET_KEY,
            algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
            audience=_audience(),
            options={"verify_iss": False},
        )
        self.assertEqual(claims["token_type"], DEVICE_ENROLLMENT_PROOF_TOKEN_TYPE)
        self.assertEqual(claims["device_id"], device.device_identifier)
        self.assertEqual(claims["profile_id"], str(self.profile.id))

    def test_current_is_not_enrolled_for_an_unknown_device(self):
        response = self.client.get(
            reverse("trusted-workspace-device-current"),
            HTTP_X_DEVICE_ID="unbound-device",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_enrolled"])
        self.assertIsNone(response.json()["binding"])

    def test_same_device_can_be_bound_to_two_workspaces(self):
        other_profile = CompanyProfile.objects.create(
            owner=self.owner,
            name="Second Workspace",
        )
        first = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="shared-device",
            created_by=self.owner,
        )
        second = TrustedWorkspaceDevice.objects.create(
            profile=other_profile,
            device_identifier="shared-device",
            created_by=self.owner,
        )

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.platform, PlatformChoices.HOSPERATOR)
        self.assertEqual(second.platform, PlatformChoices.HOSPERATOR)

    def test_revoke_is_idempotent_and_removes_current_enrollment(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="revocable-device",
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("trusted-workspace-device-revoke", kwargs={"pk": device.id}),
        )

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.is_revoked)
        self.assertFalse(device.is_active)
        self.assertEqual(device.status, "revoked")

        current = self.client.get(
            reverse("trusted-workspace-device-current"),
            HTTP_X_DEVICE_ID=device.device_identifier,
        )
        self.assertEqual(current.status_code, 200)
        self.assertFalse(current.json()["is_enrolled"])

    def test_current_returns_inactive_binding_for_reactivation(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="inactive-device",
            created_by=self.owner,
        )
        TrustedWorkspaceDevice.objects.filter(pk=device.pk).update(is_active=False)

        response = self.client.get(
            reverse("trusted-workspace-device-current"),
            HTTP_X_DEVICE_ID=device.device_identifier,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["is_enrolled"])
        self.assertEqual(payload["binding"]["id"], str(device.id))
        self.assertEqual(payload["binding"]["status"], "inactive")

    def test_duplicate_bind_returns_conflict_instead_of_server_error(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="duplicate-device",
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("trusted-workspace-device-list"),
            {
                "platform": PlatformChoices.HOSPERATOR,
                "device_identifier": device.device_identifier,
                "device_label": "Updated label",
                "capabilities": ["staff_call"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "trusted_device_binding_exists")
        self.assertEqual(response.json()["binding"]["id"], str(device.id))

    def test_reactivate_restores_existing_binding(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="reactivable-device",
            created_by=self.owner,
        )
        TrustedWorkspaceDevice.objects.filter(pk=device.pk).update(is_active=False)

        response = self.client.post(
            reverse("trusted-workspace-device-reactivate", kwargs={"pk": device.id}),
        )

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.is_active)
        self.assertFalse(device.is_revoked)
        self.assertEqual(response.json()["status"], "trusted")

    def test_reactivate_is_idempotent_for_active_binding(self):
        device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            device_identifier="already-active-device",
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("trusted-workspace-device-reactivate", kwargs={"pk": device.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(device.id))
        self.assertEqual(TrustedWorkspaceDevice.objects.filter(profile=self.profile).count(), 1)
