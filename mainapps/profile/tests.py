import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from http import HTTPStatus

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import UntypedToken

from mainapps.accounts.models import User
from mainapps.permit.models import CustomUserPermission, PermissionCategory
from mainapps.permit.models import CombinedPermissions
from mainapps.profile.models import CompanyInvitation, CompanyMembership, CompanyProfileAddress, LLMModel, LLMProviderChoices, ModelVersion, ProfileAgent
from mainapps.profile.models import CompanyProfile, StaffGroup, StaffRole, StaffRoleAssignment, SupportAccessGrant
from mainapps.profile.support_access import expire_support_grants
from mainapps.profile.support_access import expire_support_grants
from subapps.kafka.producers.identity import _serialize_company_profile


class CompanyProfileIdentityPayloadTests(SimpleTestCase):
    def test_profile_payload_includes_a_readable_headquarters_address(self):
        profile = CompanyProfile(
            id=7,
            name="QA Workspace",
            company_code="QA7",
            headquarters_address=CompanyProfileAddress(
                street_number=10,
                street="First Avenue",
                city="Lagos",
                region="Lagos",
                country="Nigeria",
                postal_code="104102",
            ),
        )

        payload = _serialize_company_profile(profile)

        self.assertEqual(
            payload["headquarters_address"],
            {
                "street_number": 10,
                "street": "First Avenue",
                "apt_number": None,
                "city": "Lagos",
                "subregion": "",
                "region": "Lagos",
                "country": "Nigeria",
                "postal_code": "104102",
            },
        )


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

    def test_staff_active_assignments_returns_active_company_memberships(self):
        invited_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Ada",
        )
        CompanyMembership.objects.create(
            user=invited_user,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
            invited_by=self.user,
        )

        response = self.client.get(f"/management/profiles/{self.profile.id}/staff_active_assignments/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        returned_emails = {item["user"]["email"] for item in payload}
        self.assertIn(self.user.email, returned_emails)
        self.assertIn(invited_user.email, returned_emails)

    def test_role_assignment_list_includes_user_and_role_name(self):
        response = self.client.get("/management/assignments/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["user"], self.user.id)
        self.assertEqual(payload[0]["role_name"], "Pharmacist")
        self.assertEqual(payload[0]["profile"], self.profile.id)


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

    @override_settings(FRONTEND_SITE_URL="https://app.interaims.test", COMPANY_INVITATION_ACCEPT_URL_TEMPLATE="")
    @patch("mainapps.profile.views.send_html_email")
    @patch("mainapps.profile.views.publish_invitation_changed")
    def test_invite_sends_company_invitation_email(self, publish_invitation_changed_mock, send_html_email_mock):
        with self.captureOnCommitCallbacks(execute=True):
            with patch("subapps.services.subscription_entitlements.enforce_subscription_limit") as enforce_limit_mock:
                response = self.client.post(
                    "/management/invitations/invite/",
                    {"email": "invitee@example.com", "role": "member"},
                    format="json",
                )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        enforce_limit_mock.assert_not_called()
        invitation = CompanyInvitation.objects.get(email="invitee@example.com")
        self.assertEqual(invitation.profile, self.profile)
        send_html_email_mock.assert_called_once()
        publish_invitation_changed_mock.assert_called_once()
        self.assertEqual(send_html_email_mock.call_args.kwargs["to_email"], ["invitee@example.com"])
        self.assertEqual(
            send_html_email_mock.call_args.kwargs["html_file"],
            "emails/company_invitation.html",
        )
        self.assertEqual(
            send_html_email_mock.call_args.kwargs["context"]["accept_url"],
            f"https://app.interaims.test/accounts/invitations/{invitation.invitation_code}",
        )

    @override_settings(FRONTEND_SITE_URL="https://app.interaims.test", COMPANY_INVITATION_ACCEPT_URL_TEMPLATE="")
    def test_invite_notifies_registered_user(self):
        invitee = User.objects.create_user(
            email="invitee@example.com",
            password="password123",
            first_name="Registered",
            last_name="Invitee",
        )

        with (
            patch("mainapps.profile.views.send_html_email") as send_html_email_mock,
            patch("mainapps.profile.views.publish_invitation_changed") as publish_invitation_changed_mock,
            patch("mainapps.profile.views.publish_invitation_notification") as publish_invitation_notification_mock,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/management/invitations/invite/",
                    {"email": "invitee@example.com", "role": "member"},
                    format="json",
                )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(publish_invitation_changed_mock.call_count, 1)
        self.assertEqual(publish_invitation_notification_mock.call_count, 1)
        notification_kwargs = publish_invitation_notification_mock.call_args.kwargs
        self.assertEqual(notification_kwargs["event_name"], "notification.identity.invitation.sent")
        self.assertIn("/accounts/invitations/", notification_kwargs["action_url"])
        send_html_email_mock.assert_called_once()

    @patch("mainapps.profile.views.send_html_email")
    @patch("mainapps.profile.views.publish_invitation_changed")
    def test_invite_resends_existing_pending_invitation_email(self, publish_invitation_changed_mock, send_html_email_mock):
        CompanyInvitation.objects.create(
            profile=self.profile,
            email="invitee@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/management/invitations/invite/",
                {"email": "invitee@example.com", "role": "member"},
                format="json",
            )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(CompanyInvitation.objects.filter(email="invitee@example.com").count(), 1)
        send_html_email_mock.assert_called_once()
        publish_invitation_changed_mock.assert_called_once()

    def test_pending_endpoint_marks_expired_invitations_before_returning(self):
        expired = CompanyInvitation.objects.create(
            profile=self.profile,
            email="expired@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        active = CompanyInvitation.objects.create(
            profile=self.profile,
            email="active@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.get("/management/invitations/pending/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        expired.refresh_from_db()
        self.assertEqual(expired.status, CompanyInvitation.InvitationStatus.EXPIRED)
        self.assertEqual([item["id"] for item in response.data], [active.id])

    @patch("mainapps.profile.views.send_html_email")
    @patch("mainapps.profile.views.publish_invitation_changed")
    def test_resend_action_sends_invitation_email(self, publish_invitation_changed_mock, send_html_email_mock):
        invitation = CompanyInvitation.objects.create(
            profile=self.profile,
            email="invitee@example.com",
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/management/invitations/{invitation.id}/resend/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CompanyInvitation.InvitationStatus.PENDING)
        send_html_email_mock.assert_called_once()
        publish_invitation_changed_mock.assert_called_once()

    @override_settings(FRONTEND_SITE_URL="https://app.interaims.test")
    def test_resend_action_notifies_registered_user(self):
        invitee = User.objects.create_user(
            email="invitee@example.com",
            password="password123",
            first_name="Registered",
            last_name="Invitee",
        )
        invitation = CompanyInvitation.objects.create(
            profile=self.profile,
            email=invitee.email,
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        with (
            patch("mainapps.profile.views.send_html_email") as send_html_email_mock,
            patch("mainapps.profile.views.publish_invitation_changed") as publish_invitation_changed_mock,
            patch("mainapps.profile.views.publish_invitation_notification") as publish_invitation_notification_mock,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f"/management/invitations/{invitation.id}/resend/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, CompanyInvitation.InvitationStatus.PENDING)
        self.assertEqual(publish_invitation_changed_mock.call_count, 1)
        self.assertEqual(publish_invitation_notification_mock.call_count, 1)
        notification_kwargs = publish_invitation_notification_mock.call_args.kwargs
        self.assertEqual(notification_kwargs["event_name"], "notification.identity.invitation.resent")
        self.assertIn("/accounts/invitations/", notification_kwargs["action_url"])
        send_html_email_mock.assert_called_once()

    def test_resolve_invitation_exposes_registration_status(self):
        invitee = User.objects.create_user(
            email="invitee@example.com",
            password="password123",
            first_name="Registered",
            last_name="Invitee",
        )
        invitation = CompanyInvitation.objects.create(
            profile=self.profile,
            email=invitee.email,
            role="member",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(
            "/management/invitations/resolve/",
            {"invitation_code": invitation.invitation_code},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["email"], invitee.email)
        self.assertTrue(payload["is_registered_user"])

    @patch("mainapps.profile.views.publish_membership_changed")
    @patch("mainapps.profile.views.publish_invitation_changed")
    def test_accept_invitation_publishes_membership_and_invitation_events(
        self,
        publish_invitation_changed_mock,
        publish_membership_changed_mock,
    ):
        invitee = User.objects.create_user(
            email="invitee@example.com",
            password="password123",
            first_name="Ada",
            last_name="Lovelace",
        )
        invitation = CompanyInvitation.objects.create(
            profile=self.profile,
            email=invitee.email,
            role=CompanyMembership.MembershipRole.MEMBER,
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )

        self.client.force_authenticate(user=invitee, token=SimpleNamespace(payload={}))
        with self.captureOnCommitCallbacks(execute=True):
            with patch("subapps.services.subscription_entitlements.enforce_subscription_limit") as enforce_limit_mock:
                response = self.client.post(
                    "/management/invitations/accept/",
                    {"invitation_code": invitation.invitation_code},
                    format="json",
                )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        enforce_limit_mock.assert_not_called()
        publish_invitation_changed_mock.assert_called_once()
        publish_membership_changed_mock.assert_called_once()


class CompanyMembershipSignalTests(TestCase):
    @patch("mainapps.profile.signals.publish_company_membership_upserted")
    @patch("mainapps.profile.signals.publish_membership_permissions_updated")
    def test_membership_permission_changes_publish_audit_and_membership_sync(
        self,
        publish_membership_permissions_updated_mock,
        publish_company_membership_upserted_mock,
    ):
        owner = User.objects.create_user(
            email="owner-membership@example.com",
            password="password123",
        )
        member = User.objects.create_user(
            email="member-membership@example.com",
            password="password123",
            first_name="Grace",
            last_name="Hopper",
        )
        profile = CompanyProfile.objects.create(owner=owner, name="Membership Audit Workspace")
        membership = CompanyMembership.objects.create(
            user=member,
            profile=profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
            invited_by=owner,
        )
        category, _ = PermissionCategory.objects.get_or_create(name="Security", defaults={"service": "services"})
        audit_permission, _ = CustomUserPermission.objects.get_or_create(
            codename=CombinedPermissions.VIEW_AUDIT_TRAIL,
            defaults={"category": category},
        )

        with self.captureOnCommitCallbacks(execute=True):
            membership.custom_permissions.set([audit_permission])

        publish_membership_permissions_updated_mock.assert_called_once()
        publish_company_membership_upserted_mock.assert_called()
        call = publish_membership_permissions_updated_mock.call_args.kwargs
        self.assertEqual(call["membership"], membership)
        self.assertEqual(call["before_permissions"], [])
        self.assertEqual(call["after_permissions"], [CombinedPermissions.VIEW_AUDIT_TRAIL])


class SupportAccessGrantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner-support@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.owner,
            name="Support Test Workspace",
        )
        self.admin_user = User.objects.create_user(
            email="admin-support@example.com",
            password="password123",
        )
        self.staff_user = User.objects.create_user(
            email="staff-support@example.com",
            password="password123",
        )
        self.support_user = User.objects.create_user(
            email="platform-support@example.com",
            password="password123",
        )
        CompanyMembership.objects.create(
            user=self.admin_user,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.ADMIN,
            is_active=True,
            invited_by=self.owner,
        )
        CompanyMembership.objects.create(
            user=self.staff_user,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
            invited_by=self.owner,
        )

    def _force_profile_auth(self, user, *, permissions=None, owner_id=None):
        payload = {
            "profile_id": self.profile.id,
            "permissions": list(permissions or []),
            "owner_id": str(owner_id) if owner_id else str(self.profile.owner_id),
        }
        self.client.force_authenticate(user=user, token=SimpleNamespace(payload=payload))

    def _grant_payload(self, **overrides):
        payload = {
            "grantee_email": self.support_user.email,
            "reason": "Investigate checkout and stock sync issue",
            "permission_mode": "support_readonly",
            "membership_role": CompanyMembership.MembershipRole.MEMBER,
            "expires_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        }
        payload.update(overrides)
        return payload

    def _create_support_grant(self, **overrides):
        values = {
            "profile": self.profile,
            "grantee_user": self.support_user,
            "accepted_by": self.support_user,
            "grantee_email_snapshot": self.support_user.email,
            "created_by": self.owner,
            "approved_by": self.owner,
            "reason": "Investigate issue",
            "permission_mode": "support_readonly",
            "membership_role": CompanyMembership.MembershipRole.MEMBER,
            "starts_at": timezone.now() - timedelta(minutes=5),
            "expires_at": timezone.now() + timedelta(hours=2),
        }
        values.update(overrides)
        return SupportAccessGrant.objects.create(**values)

    @override_settings(FRONTEND_SITE_URL="https://app.interaims.test")
    @patch("mainapps.profile.views.publish_support_access_grant_created")
    @patch("mainapps.profile.views.send_html_email")
    def test_owner_can_create_support_access_request(self, send_html_email_mock, publish_created_mock):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)

        response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get()
        self.assertEqual(grant.profile, self.profile)
        self.assertEqual(grant.grantee_user, self.support_user)
        self.assertEqual(grant.created_by, self.owner)
        self.assertEqual(grant.current_status, SupportAccessGrant.Status.PENDING)
        send_html_email_mock.assert_called_once()
        publish_created_mock.assert_called_once()
        self.assertEqual(send_html_email_mock.call_args.kwargs["html_file"], "emails/support_access_request.html")
        self.assertEqual(
            send_html_email_mock.call_args.kwargs["context"]["accept_url"],
            f"https://app.interaims.test/accounts/support-access/{grant.invitation_code}",
        )

    @patch("mainapps.profile.views.send_html_email")
    def test_admin_with_support_access_permission_can_create_request(self, send_html_email_mock):
        self._force_profile_auth(
            self.admin_user,
            permissions=[CombinedPermissions.CREATE_SUPPORT_ACCESS_GRANT],
        )

        response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(ticket_reference="SUP-123"),
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get(ticket_reference="SUP-123")
        self.assertEqual(grant.created_by, self.admin_user)
        self.assertEqual(grant.current_status, SupportAccessGrant.Status.PENDING)
        send_html_email_mock.assert_called_once()

    def test_unauthorized_staff_cannot_create_support_access_grant(self):
        self._force_profile_auth(self.staff_user)

        response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(SupportAccessGrant.objects.count(), 0)

    def test_overlapping_pending_request_is_rejected(self):
        self._create_support_grant(
            grantee_user=None,
            accepted_by=None,
            starts_at=timezone.now() - timedelta(minutes=10),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self._force_profile_auth(self.owner, owner_id=self.owner.id)

        response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(
                starts_at=(timezone.now() - timedelta(minutes=5)).isoformat(),
                expires_at=(timezone.now() + timedelta(hours=3)).isoformat(),
            ),
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("non_field_errors", response.json())

    def test_pending_request_cannot_switch_workspace_before_acceptance(self):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        create_response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(),
            format="json",
        )
        self.assertEqual(create_response.status_code, HTTPStatus.CREATED)

        self.client.force_authenticate(user=self.support_user, token=SimpleNamespace(payload={}))
        response = self.client.post(
            "/auth/switch-company/",
            {"profile_id": str(self.profile.id)},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    @patch("mainapps.accounts.views.publish_support_access_workspace_entered")
    @patch("mainapps.profile.views.publish_support_access_grant_activated")
    def test_existing_user_can_accept_request_and_switch_workspace(
        self,
        publish_activated_mock,
        publish_workspace_entered_mock,
    ):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        create_response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(permission_mode="support_inventory_ops"),
            format="json",
        )
        self.assertEqual(create_response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get()

        self.client.force_authenticate(user=self.support_user, token=SimpleNamespace(payload={}))
        accept_response = self.client.post(
            "/management/support-access-grants/accept/",
            {"invitation_code": grant.invitation_code},
            format="json",
        )

        self.assertEqual(accept_response.status_code, HTTPStatus.OK)
        grant.refresh_from_db()
        self.assertEqual(grant.current_status, SupportAccessGrant.Status.ACTIVE)
        self.assertEqual(grant.accepted_by, self.support_user)
        publish_activated_mock.assert_called_once()

        response = self.client.post(
            "/auth/switch-company/",
            {"profile_id": str(self.profile.id), "support_access_grant_id": str(grant.id)},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertTrue(payload["profile_context"]["support_access"])
        self.assertEqual(payload["profile_context"]["support_access_grant_id"], str(grant.id))
        access_claims = UntypedToken(payload["access"]).payload
        self.assertEqual(access_claims["support_access_grant_id"], str(grant.id))
        self.assertEqual(access_claims["support_access_mode"], "support_inventory_ops")
        self.assertEqual(access_claims["support_actor_type"], "support")
        self.assertIn(CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY, access_claims["support_access_scope"])
        grant.refresh_from_db()
        self.assertIsNotNone(grant.last_used_at)
        publish_workspace_entered_mock.assert_called_once()

    def test_wrong_email_cannot_accept_request(self):
        outsider = User.objects.create_user(email="outsider@example.com", password="password123")
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        create_response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(),
            format="json",
        )
        self.assertEqual(create_response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get()

        self.client.force_authenticate(user=outsider, token=SimpleNamespace(payload={}))
        accept_response = self.client.post(
            "/management/support-access-grants/accept/",
            {"invitation_code": grant.invitation_code},
            format="json",
        )

        self.assertEqual(accept_response.status_code, HTTPStatus.BAD_REQUEST)
        grant.refresh_from_db()
        self.assertEqual(grant.current_status, SupportAccessGrant.Status.PENDING)

    def test_unregistered_email_can_register_and_accept_request(self):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        create_response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(grantee_email="new.support@example.com"),
            format="json",
        )
        self.assertEqual(create_response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get(grantee_email_snapshot="new.support@example.com")
        self.assertIsNone(grant.grantee_user)

        new_user = User.objects.create_user(email="new.support@example.com", password="password123")
        self.client.force_authenticate(user=new_user, token=SimpleNamespace(payload={}))
        accept_response = self.client.post(
            "/management/support-access-grants/accept/",
            {"invitation_code": grant.invitation_code},
            format="json",
        )

        self.assertEqual(accept_response.status_code, HTTPStatus.OK)
        grant.refresh_from_db()
        self.assertEqual(grant.grantee_user, new_user)
        self.assertEqual(grant.current_status, SupportAccessGrant.Status.ACTIVE)

    def test_expired_grant_blocks_workspace_switch(self):
        self._create_support_grant(
            starts_at=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.client.force_authenticate(user=self.support_user, token=SimpleNamespace(payload={}))

        response = self.client.post(
            "/auth/switch-company/",
            {"profile_id": str(self.profile.id)},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_revoked_grant_blocks_refresh_and_reentry(self):
        grant = self._create_support_grant()

        login_response = self.client.post(
            "/auth/login/",
            {
                "email": self.support_user.email,
                "password": "password123",
                "profile_id": str(self.profile.id),
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, HTTPStatus.OK)
        refresh_token = login_response.json()["refresh"]

        grant.revoke(revoked_by=self.owner)

        refresh_response = self.client.post(
            "/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, HTTPStatus.BAD_REQUEST)

        self.client.force_authenticate(user=self.support_user, token=SimpleNamespace(payload={}))
        reentry_response = self.client.post(
            "/auth/switch-company/",
            {"profile_id": str(self.profile.id)},
            format="json",
        )
        self.assertEqual(reentry_response.status_code, HTTPStatus.BAD_REQUEST)

    @patch("mainapps.profile.views.publish_support_access_grant_declined")
    def test_declined_request_cannot_be_used(self, publish_declined_mock):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        create_response = self.client.post(
            "/management/support-access-grants/",
            self._grant_payload(),
            format="json",
        )
        self.assertEqual(create_response.status_code, HTTPStatus.CREATED)
        grant = SupportAccessGrant.objects.get()

        self.client.force_authenticate(user=self.support_user, token=SimpleNamespace(payload={}))
        decline_response = self.client.post(
            "/management/support-access-grants/decline/",
            {"invitation_code": grant.invitation_code},
            format="json",
        )
        self.assertEqual(decline_response.status_code, HTTPStatus.OK)
        publish_declined_mock.assert_called_once()

        switch_response = self.client.post(
            "/auth/switch-company/",
            {"profile_id": str(self.profile.id)},
            format="json",
        )
        self.assertEqual(switch_response.status_code, HTTPStatus.BAD_REQUEST)

    @patch("mainapps.profile.views.publish_support_access_grant_extended")
    def test_owner_can_extend_support_access_request(self, publish_extended_mock):
        grant = self._create_support_grant()
        self._force_profile_auth(self.owner, owner_id=self.owner.id)

        response = self.client.post(
            f"/management/support-access-grants/{grant.id}/extend/",
            {
                "expires_at": (timezone.now() + timedelta(hours=4)).isoformat(),
                "notes": "Need more time for investigation",
            },
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        publish_extended_mock.assert_called_once()

    @patch("mainapps.profile.views.publish_support_access_grant_revoked")
    def test_owner_can_revoke_support_access_request(self, publish_revoked_mock):
        grant = self._create_support_grant()
        self._force_profile_auth(self.owner, owner_id=self.owner.id)

        response = self.client.post(
            f"/management/support-access-grants/{grant.id}/revoke/",
            {"notes": "Issue resolved"},
            format="json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        publish_revoked_mock.assert_called_once()

    @patch("mainapps.profile.support_access.publish_support_access_grant_expired")
    def test_expire_support_grants_publishes_expired_event(self, publish_expired_mock):
        grant = self._create_support_grant(
            starts_at=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        SupportAccessGrant.objects.filter(id=grant.id).update(status=SupportAccessGrant.Status.ACTIVE)

        expired_count = expire_support_grants(profile=self.profile)

        self.assertEqual(expired_count, 1)
        grant.refresh_from_db()
        self.assertEqual(grant.status, SupportAccessGrant.Status.EXPIRED)
        publish_expired_mock.assert_called_once()
        published_grant = publish_expired_mock.call_args.args[0]
        self.assertEqual(published_grant.id, grant.id)

    @patch("mainapps.accounts.views.publish_support_access_workspace_exited")
    def test_logout_from_support_context_publishes_workspace_exit(self, publish_workspace_exited_mock):
        grant = self._create_support_grant()
        self.client.force_authenticate(
            user=self.support_user,
            token=SimpleNamespace(
                payload={"profile_id": self.profile.id, "support_access_grant_id": str(grant.id)}
            ),
        )

        response = self.client.post("/auth/logout/", format="json")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        publish_workspace_exited_mock.assert_called_once()

    def test_support_user_lookup_returns_matching_non_member_candidates(self):
        self._force_profile_auth(self.owner, owner_id=self.owner.id)
        outsider = User.objects.create_user(
            email="support.lookup@example.com",
            password="password123",
            first_name="Support",
            last_name="Lookup",
        )

        response = self.client.get("/management/support-access-grants/support-users/?q=lookup")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        returned_emails = {item["email"] for item in payload}
        self.assertIn(outsider.email, returned_emails)
        self.assertNotIn(self.staff_user.email, returned_emails)


class InternalHosperatorGroupMembersTests(TestCase):
    service_token = "notification-service-test-token"

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(email="group-owner@example.com", password="password123")
        self.profile = CompanyProfile.objects.create(owner=self.owner, name="Notification Hospital")
        self.active_member = User.objects.create_user(email="group-member@example.com", password="password123")
        self.inactive_membership_user = User.objects.create_user(
            email="group-inactive-membership@example.com", password="password123"
        )
        self.disabled_user = User.objects.create_user(email="group-disabled@example.com", password="password123")
        self.disabled_user.is_active = False
        self.disabled_user.save(update_fields=["is_active"])
        for user, is_active in (
            (self.active_member, True),
            (self.inactive_membership_user, False),
            (self.disabled_user, True),
        ):
            CompanyMembership.objects.create(
                user=user,
                profile=self.profile,
                role=CompanyMembership.MembershipRole.MEMBER,
                is_active=is_active,
                invited_by=self.owner,
            )
        self.group = StaffGroup.objects.create(
            profile=self.profile,
            name="Duty Managers",
            created_by=self.owner,
        )
        self.group.users.add(self.owner, self.active_member, self.inactive_membership_user, self.disabled_user)
        self.path = f"/management/internal/profiles/{self.profile.id}/groups/{self.group.id}/members/"

    def _get(self, path=None, token=None):
        headers = {}
        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.get(path or self.path, **headers)

    @patch.dict(os.environ, {"HOSPERATOR_NOTIFICATION_SERVICE_TOKEN": service_token})
    def test_returns_only_active_profile_group_members_in_contract_shape(self):
        response = self._get(token=self.service_token)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {
                "profile_id": self.profile.id,
                "group_id": str(self.group.id),
                "member_user_ids": [str(self.owner.id), str(self.active_member.id)],
            },
        )

    @patch.dict(os.environ, {"HOSPERATOR_NOTIFICATION_SERVICE_TOKEN": service_token})
    def test_rejects_missing_or_invalid_service_bearer_token(self):
        self.assertEqual(self._get().status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(self._get(token="wrong-token").status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(self._get(token=self.service_token).status_code, HTTPStatus.OK)

    @patch.dict(os.environ, {"HOSPERATOR_NOTIFICATION_SERVICE_TOKEN": service_token})
    def test_hides_cross_profile_or_inactive_group_as_not_found(self):
        other_profile = CompanyProfile.objects.create(owner=self.owner, name="Other Hospital")
        cross_profile_path = (
            f"/management/internal/profiles/{other_profile.id}/groups/{self.group.id}/members/"
        )
        self.assertEqual(self._get(path=cross_profile_path, token=self.service_token).status_code, HTTPStatus.NOT_FOUND)

        self.group.is_active = False
        self.group.save(update_fields=["is_active"])
        self.assertEqual(self._get(token=self.service_token).status_code, HTTPStatus.NOT_FOUND)

    @patch.dict(os.environ, {"HOSPERATOR_NOTIFICATION_SERVICE_TOKEN": service_token})
    def test_rejects_group_larger_than_notification_contract_capacity(self):
        users = [
            User(email=f"bounded-group-{index}@example.com", username=f"bounded-group-{index}")
            for index in range(201)
        ]
        User.objects.bulk_create(users)
        CompanyMembership.objects.bulk_create(
            [
                CompanyMembership(
                    user=user,
                    profile=self.profile,
                    role=CompanyMembership.MembershipRole.MEMBER,
                    is_active=True,
                    invited_by=self.owner,
                )
                for user in users
            ]
        )
        self.group.users.add(*users)

        response = self._get(token=self.service_token)

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json(), {"detail": "Group exceeds the operational notification membership limit."})
