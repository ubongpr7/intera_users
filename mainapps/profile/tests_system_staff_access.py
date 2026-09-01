from django.core.exceptions import ValidationError
from django.test import TestCase

from mainapps.accounts.models import User
from mainapps.accounts.serializers import MyTokenObtainPairSerializer
from mainapps.permit.models import CustomUserPermission, PermissionCategory
from mainapps.profile.default_staff_presets import sync_system_staff_groups, sync_system_staff_roles
from mainapps.profile.models import CompanyProfile, StaffGroup, StaffRole, StaffRoleAssignment


class SystemStaffAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner-system@example.com", password="password123")
        self.member = User.objects.create_user(email="member-system@example.com", password="password123")
        self.profile = CompanyProfile.objects.create(owner=self.owner, name="System Access Workspace")

    def test_sync_creates_one_universal_role_and_group(self):
        sync_system_staff_roles()
        sync_system_staff_groups()

        self.assertEqual(StaffRole.objects.filter(name="Cashier").count(), 1)
        self.assertEqual(StaffGroup.objects.filter(name="Cashier").count(), 1)
        self.assertIsNone(StaffRole.objects.get(name="Cashier").profile_id)
        self.assertTrue(StaffGroup.objects.get(name="Cashier").is_system)

    def test_system_definitions_cannot_be_edited_or_receive_changed_permissions(self):
        role = StaffRole.objects.create(name="Universal", is_system=True, profile=None)
        role.name = "Changed"
        with self.assertRaises(ValidationError):
            role.save()

        group = StaffGroup.objects.create(name="Universal Group", is_system=True, profile=None)
        group.profile = self.profile
        with self.assertRaises(ValidationError):
            group.save()

    def test_universal_role_can_be_assigned_in_a_workspace(self):
        role = StaffRole.objects.create(name="Universal", is_system=True, profile=None)
        assignment = StaffRoleAssignment.objects.create(
            profile=self.profile,
            user=self.member,
            role=role,
            assigned_by=self.owner,
        )
        self.assertEqual(assignment.role_id, role.id)
        self.assertEqual(assignment.profile_id, self.profile.id)

    def test_authorization_resolution_includes_universal_system_role_and_group(self):
        permission, _ = CustomUserPermission.objects.get_or_create(
            codename="read_universal_access_test",
            defaults={"category": PermissionCategory.objects.create(name="Universal Access")},
        )
        role = StaffRole.objects.create(name="Universal Role", is_system=True, profile=None)
        role.permissions.add(permission)
        group = StaffGroup.objects.create(name="Universal Group", is_system=True, profile=None)
        group.permissions.add(permission)
        self.member.staff_groups.add(group)
        StaffRoleAssignment.objects.create(
            profile=self.profile,
            user=self.member,
            role=role,
            assigned_by=self.owner,
        )

        permissions = MyTokenObtainPairSerializer.get_all_permissions(self.member, profile=self.profile)

        self.assertEqual(permissions, [permission.codename])
