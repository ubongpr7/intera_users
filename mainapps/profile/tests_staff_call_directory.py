from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from mainapps.accounts.authorization_context import issue_authorization_context
from mainapps.accounts.models import User
from mainapps.accounts.serializers import MyTokenObtainPairSerializer
from mainapps.permit.models import PlatformChoices
from mainapps.profile.models import CompanyMembership, CompanyProfile, TrustedWorkspaceDevice


class StaffCallDirectoryApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="directory-owner@example.com",
            password="password123",
            first_name="Ada",
            last_name="Owner",
        )
        self.member = User.objects.create_user(
            email="directory-member@example.com",
            password="password123",
            first_name="Chidi",
            last_name="Nurse",
        )
        self.profile = CompanyProfile.objects.create(owner=self.owner, name="Directory Hospital")
        CompanyMembership.objects.update_or_create(
            user=self.owner,
            profile=self.profile,
            defaults={"role": CompanyMembership.MembershipRole.OWNER, "is_active": True},
        )
        CompanyMembership.objects.create(
            user=self.member,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.MEMBER,
        )
        self.device = TrustedWorkspaceDevice.objects.create(
            profile=self.profile,
            platform=PlatformChoices.HOSPERATOR,
            device_identifier="ward-phone",
            device_label="Ward phone",
            capabilities=["staff_call"],
            created_by=self.owner,
            last_seen_by_user=self.member,
            last_seen_at=timezone.now(),
        )

        _refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            self.member,
            self.profile,
            platform=PlatformChoices.HOSPERATOR,
        )
        context = issue_authorization_context(
            self.member,
            profile=self.profile,
            platform=PlatformChoices.HOSPERATOR,
            access_token_id=access.get("jti"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.member, token=access)
        self.context_header = context

    def test_active_member_can_read_bounded_calling_projection_without_admin_permission(self):
        response = self.client.get(
            reverse("company-profile-staff-call-directory", kwargs={"pk": self.profile.id}),
            HTTP_X_INTERA_AUTHORIZATION_CONTEXT=self.context_header,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["organisation_id"], str(self.profile.id))
        self.assertEqual(payload["count"], 2)
        member = next(item for item in payload["results"] if item["staff_id"] == str(self.member.id))
        self.assertEqual(member["display_name"], "Chidi Nurse")
        self.assertTrue(member["enrolled_device_presence"]["is_present"])
        self.assertEqual(member["enrolled_device_presence"]["active_device_count"], 1)
        self.assertEqual(member["enrolled_device_presence"]["capabilities"], ["staff_call"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_directory_rejects_context_from_another_access_token(self):
        _refresh, other_access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            self.member,
            self.profile,
            platform=PlatformChoices.HOSPERATOR,
        )
        self.client.force_authenticate(user=self.member, token=other_access)

        response = self.client.get(
            reverse("company-profile-staff-call-directory", kwargs={"pk": self.profile.id}),
            HTTP_X_INTERA_AUTHORIZATION_CONTEXT=self.context_header,
        )

        self.assertEqual(response.status_code, 401)
