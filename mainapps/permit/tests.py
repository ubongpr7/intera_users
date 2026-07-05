from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from mainapps.accounts.models import User
from mainapps.permit.models import CustomUserPermission, PermissionCategory
from mainapps.profile.models import CompanyProfile
from mainapps.profile.models import CompanyMembership, StaffGroup, StaffRole, StaffRoleAssignment
from mainapps.permit.api.views import UserAccessViewSet, _user_has_profile_access
from subapps.kafka.producers.access_control import (
    publish_group_permissions_updated,
    publish_role_permissions_updated,
    publish_user_groups_updated,
    publish_user_permissions_updated,
)


class AccessControlProducerTests(TestCase):
    @patch("subapps.kafka.producers.access_control.publish_workspace_notification")
    @patch("subapps.kafka.producers.access_control.publish_audit_fact")
    def test_publish_user_permissions_updated_resolves_callable_user_name(
        self,
        publish_audit_fact_mock,
        publish_workspace_notification_mock,
    ):
        user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            first_name="Ada",
            last_name="Lovelace",
        )
        profile = CompanyProfile.objects.create(
            owner=user,
            name="Acme Health",
        )

        publish_user_permissions_updated(
            profile=profile,
            actor={"user_id": str(user.id), "email": user.email, "name": "Owner"},
            user=user,
            before_permissions=["read_company"],
            after_permissions=["read_company", "manage_company_settings"],
        )

        audit_payload = publish_audit_fact_mock.call_args.kwargs
        notification_payload = publish_workspace_notification_mock.call_args.kwargs

        self.assertEqual(audit_payload["target"]["label"], "Ada Lovelace")
        self.assertEqual(notification_payload["user_ids"], [str(user.id)])

    @patch("subapps.kafka.producers.access_control.publish_workspace_notification")
    @patch("subapps.kafka.producers.access_control.publish_audit_fact")
    def test_publish_group_permissions_updated_includes_affected_user_identity(
        self,
        publish_audit_fact_mock,
        publish_workspace_notification_mock,
    ):
        owner = User.objects.create_user(
            email="owner@example.com",
            password="password123",
            first_name="Owner",
            last_name="User",
        )
        member = User.objects.create_user(
            email="member@example.com",
            password="password123",
            first_name="Member",
            last_name="User",
        )
        profile = CompanyProfile.objects.create(owner=owner, name="Acme Health")
        group = StaffGroup.objects.create(profile=profile, name="Front Store", created_by=owner)
        group.users.add(member)

        publish_group_permissions_updated(
            actor={"user_id": str(owner.id), "email": owner.email, "name": "Owner User"},
            group=group,
            before_permissions=["read_pos"],
            after_permissions=["read_pos", "view_audit_trail"],
        )

        audit_payload = publish_audit_fact_mock.call_args.kwargs
        notification_payload = publish_workspace_notification_mock.call_args.kwargs

        self.assertEqual(audit_payload["payload"]["affected_users"][0]["user_email"], "member@example.com")
        self.assertEqual(notification_payload["metadata"]["affected_users"][0]["user_name"], "Member User")
        self.assertEqual(notification_payload["user_ids"], [str(member.id)])

    @patch("subapps.kafka.producers.access_control.publish_workspace_notification")
    @patch("subapps.kafka.producers.access_control.publish_audit_fact")
    def test_publish_role_permissions_updated_includes_affected_user_identity(
        self,
        publish_audit_fact_mock,
        publish_workspace_notification_mock,
    ):
        owner = User.objects.create_user(
            email="owner-role@example.com",
            password="password123",
            first_name="Owner",
            last_name="Role",
        )
        member = User.objects.create_user(
            email="role-member@example.com",
            password="password123",
            first_name="Role",
            last_name="Member",
        )
        profile = CompanyProfile.objects.create(owner=owner, name="Role Acme")
        role = StaffRole.objects.create(profile=profile, name="Supervisor", created_by=owner)
        StaffRoleAssignment.objects.create(profile=profile, user=member, role=role, assigned_by=owner)

        publish_role_permissions_updated(
            actor={"user_id": str(owner.id), "email": owner.email, "name": "Owner Role"},
            role=role,
            before_permissions=["read_inventory"],
            after_permissions=["read_inventory", "view_audit_trail"],
        )

        audit_payload = publish_audit_fact_mock.call_args.kwargs
        notification_payload = publish_workspace_notification_mock.call_args.kwargs

        self.assertEqual(audit_payload["payload"]["affected_users"][0]["user_email"], "role-member@example.com")
        self.assertEqual(notification_payload["metadata"]["affected_users"][0]["user_name"], "Role Member")
        self.assertEqual(notification_payload["user_ids"], [str(member.id)])


class PermitApiViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = APIRequestFactory()
        self.owner = User.objects.create_superuser(
            email="owner-permit@example.com",
            password="password123",
        )
        self.active_profile = CompanyProfile.objects.create(owner=self.owner, name="Active Permit Workspace")
        self.other_profile = CompanyProfile.objects.create(owner=self.owner, name="Other Permit Workspace")
        self.member = User.objects.create_user(
            email="member-permit@example.com",
            password="password123",
            profile=self.other_profile,
            first_name="Permit",
            last_name="Member",
        )
        CompanyMembership.objects.create(
            user=self.member,
            profile=self.active_profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
            invited_by=self.owner,
        )
        self.auth_token = SimpleNamespace(payload={"profile_id": str(self.active_profile.id), "owner_id": str(self.owner.id)})
        self.client.force_authenticate(user=self.owner, token=self.auth_token)
        self.permission_category, _ = PermissionCategory.objects.get_or_create(
            name="Security",
            defaults={"service": "users"},
        )

    def test_user_profile_access_recognizes_active_company_membership_even_when_profile_pointer_diff(self):
        self.assertTrue(_user_has_profile_access(self.member, self.active_profile))

    @patch("mainapps.permit.api.views.publish_user_permissions_updated")
    @patch("mainapps.permit.api.views.UserAccessViewSet.get_object")
    def test_user_permission_update_uses_company_membership_scope(
        self,
        get_object_mock,
        publish_user_permissions_updated_mock,
    ):
        audit_permission, _ = CustomUserPermission.objects.get_or_create(
            codename="view_audit_trail",
            defaults={"category": self.permission_category},
        )
        get_object_mock.return_value = self.member

        request = self.factory.put(
            f"/permission_api/users/{self.member.id}/permissions/",
            {"permissions": [audit_permission.codename]},
            format="json",
        )
        force_authenticate(request, user=self.owner, token=self.auth_token)
        with self.captureOnCommitCallbacks(execute=True):
            response = UserAccessViewSet.as_view({"put": "permissions"})(request, pk=str(self.member.id))

        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(
            sorted(self.member.custom_permissions.values_list("codename", flat=True)),
            [audit_permission.codename],
        )
        publish_user_permissions_updated_mock.assert_called_once()
        call = publish_user_permissions_updated_mock.call_args.kwargs
        self.assertEqual(call["profile"], self.active_profile)
        self.assertEqual(call["user"], self.member)
        self.assertEqual(call["before_permissions"], [])
        self.assertEqual(call["after_permissions"], [audit_permission.codename])

    @patch("mainapps.permit.api.views.publish_user_groups_updated")
    @patch("mainapps.permit.api.views.UserAccessViewSet.get_object")
    def test_user_group_update_only_audits_groups_from_active_profile(
        self,
        get_object_mock,
        publish_user_groups_updated_mock,
    ):
        active_existing_group = StaffGroup.objects.create(
            profile=self.active_profile,
            name="Active Existing Group",
            created_by=self.owner,
        )
        active_replacement_group = StaffGroup.objects.create(
            profile=self.active_profile,
            name="Active Replacement Group",
            created_by=self.owner,
        )
        other_profile_group = StaffGroup.objects.create(
            profile=self.other_profile,
            name="Other Profile Group",
            created_by=self.owner,
        )
        self.member.staff_groups.add(active_existing_group, other_profile_group)
        get_object_mock.return_value = self.member

        request = self.factory.put(
            f"/permission_api/users/{self.member.id}/groups/",
            {"groups": [str(active_replacement_group.id)]},
            format="json",
        )
        force_authenticate(request, user=self.owner, token=self.auth_token)
        with self.captureOnCommitCallbacks(execute=True):
            response = UserAccessViewSet.as_view({"put": "groups"})(request, pk=str(self.member.id))

        self.assertEqual(response.status_code, 200)
        publish_user_groups_updated_mock.assert_called_once()
        call = publish_user_groups_updated_mock.call_args.kwargs
        self.assertEqual(call["profile"], self.active_profile)
        self.assertEqual(call["user"], self.member)
        self.assertEqual(call["before_groups"], ["Active Existing Group"])
        self.assertEqual(call["after_groups"], ["Active Replacement Group"])
