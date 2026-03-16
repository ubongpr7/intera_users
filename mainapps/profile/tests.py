from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from http import HTTPStatus

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyInvitation, LLMModel, LLMProviderChoices, ModelVersion, ProfileAgent
from mainapps.profile.models import CompanyProfile, StaffGroup, StaffRole, StaffRoleAssignment


class ProfileAgentModelTests(SimpleTestCase):
    def test_effective_base_url_prefers_agent_override(self):
        llm = LLMModel(provider=LLMProviderChoices.gpt, base_url="https://api.openai.com")
        version = ModelVersion(llm=llm, model_name="gpt-5-mini")
        agent = ProfileAgent(version=version, base_url="https://custom-openai.example.com")

        self.assertEqual(agent.effective_base_url, "https://custom-openai.example.com")

    def test_effective_base_url_falls_back_to_provider_default(self):
        llm = LLMModel(provider=LLMProviderChoices.gpt, base_url="https://api.openai.com")
        version = ModelVersion(llm=llm, model_name="gpt-5-mini")
        agent = ProfileAgent(version=version, base_url="")

        self.assertEqual(agent.effective_base_url, "https://api.openai.com")


class CompanyProfileActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.user,
            name="Acme Health",
        )
        self.auth_token = SimpleNamespace(payload={"profile_id": self.profile.id})
        self.client.force_authenticate(user=self.user, token=self.auth_token)
        self.active_role = StaffRole.objects.create(
            profile=self.profile,
            name="Pharmacist",
            is_active=True,
            created_by=self.user,
        )
        self.inactive_role = StaffRole.objects.create(
            profile=self.profile,
            name="Auditor",
            is_active=False,
            created_by=self.user,
        )
        self.active_group = StaffGroup.objects.create(
            profile=self.profile,
            name="Operations",
            is_active=True,
            created_by=self.user,
        )
        self.inactive_group = StaffGroup.objects.create(
            profile=self.profile,
            name="Archived",
            is_active=False,
            created_by=self.user,
        )
        StaffRoleAssignment.objects.create(
            profile=self.profile,
            user=self.user,
            role=self.active_role,
            is_active=True,
            assigned_by=self.user,
        )

    def test_roles_action_returns_profile_roles(self):
        response = self.client.get(f"/management/profiles/{self.profile.id}/roles/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            {item["name"] for item in response.json()},
            {"Pharmacist", "Auditor"},
        )

    def test_groups_action_returns_profile_groups(self):
        response = self.client.get(f"/management/profiles/{self.profile.id}/groups/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            {item["name"] for item in response.json()},
            {"Operations", "Archived"},
        )

    def test_analytics_action_uses_profile_role_and_group_helpers(self):
        response = self.client.get(f"/management/profiles/{self.profile.id}/analytics/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json(),
            {
                "total_staff": 1,
                "active_roles": 1,
                "active_groups": 1,
                "total_addresses": 0,
                "total_policies": 0,
                "verification_status": False,
                "profile_age_days": 0,
            },
        )


class CompanyInvitationActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            email="owner@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.user,
            name="Acme Health",
        )
        self.auth_token = SimpleNamespace(payload={"profile_id": self.profile.id})
        self.client.force_authenticate(user=self.user, token=self.auth_token)

    @patch("mainapps.profile.views.send_html_email")
    def test_invite_sends_company_invitation_email(self, send_html_email_mock):
        response = self.client.post(
            "/management/invitations/invite/",
            {"email": "invitee@example.com", "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        invitation = CompanyInvitation.objects.get(email="invitee@example.com")
        self.assertEqual(invitation.profile, self.profile)
        send_html_email_mock.assert_called_once()
        self.assertEqual(send_html_email_mock.call_args.kwargs["to_email"], ["invitee@example.com"])
        self.assertEqual(
            send_html_email_mock.call_args.kwargs["html_file"],
            "emails/company_invitation.html",
        )

    @patch("mainapps.profile.views.send_html_email")
    def test_invite_resends_existing_pending_invitation_email(self, send_html_email_mock):
        CompanyInvitation.objects.create(
            profile=self.profile,
            email="invitee@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.post(
            "/management/invitations/invite/",
            {"email": "invitee@example.com", "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(CompanyInvitation.objects.filter(email="invitee@example.com").count(), 1)
        send_html_email_mock.assert_called_once()

    @patch("mainapps.profile.views.send_html_email")
    def test_resend_action_sends_invitation_email(self, send_html_email_mock):
        invitation = CompanyInvitation.objects.create(
            profile=self.profile,
            email="invitee@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.post(f"/management/invitations/{invitation.id}/resend/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CompanyInvitation.InvitationStatus.PENDING)
        send_html_email_mock.assert_called_once()
