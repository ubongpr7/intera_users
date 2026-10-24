import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from mainapps.accounts.models import User
from mainapps.profile.models import (
    CompanyMembership,
    CompanyProfile,
    StaffGroup,
    StaffRole,
    StaffRoleAssignment,
)


@override_settings(IS_PRODUCTION=False)
class HosperatorDemoStaffSeedTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.com", password="secret")
        self.profile = CompanyProfile.objects.create(owner=self.owner, name="Hosperator Dev QA Hospital")
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manifest_path = Path(self.temp_dir.name) / "manifest.json"
        self.manifest_path.write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "external_delivery_allowed": False,
                    "seed_key": "pitch-demo-v1",
                    "profile_id": self.profile.id,
                    "staff": [
                        {
                            "email": "pitch-demo-v1.staff-001@example.invalid",
                            "first_name": "Demo-Amina",
                            "last_name": "Bello",
                            "role": "Hosperator Receptionist",
                            "group": "Front Desk",
                            "can_sign_in": False,
                        },
                        {
                            "email": "pitch-demo-v1.staff-002@example.invalid",
                            "first_name": "Demo-Chinedu",
                            "last_name": "Okeke",
                            "role": "Hosperator Nurse",
                            "group": "Ward Nursing",
                            "can_sign_in": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    def run_command(self, *, apply=False):
        options = {
            "profile_id": self.profile.id,
            "expected_profile_name": self.profile.name,
            "manifest": self.manifest_path,
        }
        if apply:
            options["apply"] = True
        with patch.dict(os.environ, {"HOSPERATOR_ALLOW_SYNTHETIC_DEMO_DATA": "true"}):
            call_command("seed_hosperator_demo_staff", **options)

    def test_dry_run_writes_nothing(self):
        self.run_command()
        self.assertFalse(User.objects.filter(email__endswith="@example.invalid").exists())

    def test_apply_is_silent_non_login_and_idempotent(self):
        receipt_path = Path(self.temp_dir.name) / "receipt.json"
        with patch.dict(os.environ, {"HOSPERATOR_ALLOW_SYNTHETIC_DEMO_DATA": "true"}):
            call_command(
                "seed_hosperator_demo_staff",
                profile_id=self.profile.id,
                expected_profile_name=self.profile.name,
                manifest=self.manifest_path,
                receipt=receipt_path,
                apply=True,
            )
        self.run_command(apply=True)

        staff = User.objects.filter(email__endswith="@example.invalid").order_by("email")
        self.assertEqual(staff.count(), 2)
        self.assertTrue(all(not user.has_usable_password() for user in staff))
        self.assertEqual(
            CompanyMembership.objects.filter(profile=self.profile, user__in=staff, is_active=True).count(),
            2,
        )
        self.assertEqual(
            StaffRoleAssignment.objects.filter(profile=self.profile, user__in=staff, is_active=True).count(),
            2,
        )
        expected_group_roles = {
            "Front Desk": "Hosperator Receptionist",
            "Ward Nursing": "Hosperator Nurse",
        }
        for group_name, role_name in expected_group_roles.items():
            group_permissions = set(
                StaffGroup.objects.get(profile=self.profile, name=group_name).permissions.values_list(
                    "codename", flat=True
                )
            )
            role_permissions = set(
                StaffRole.objects.get(profile__isnull=True, name=role_name).permissions.values_list(
                    "codename", flat=True
                )
            )
            self.assertTrue(group_permissions)
            self.assertEqual(group_permissions, role_permissions)
            system_group_permissions = set(
                StaffGroup.objects.get(
                    profile__isnull=True,
                    is_system=True,
                    name=role_name,
                ).permissions.values_list("codename", flat=True)
            )
            self.assertEqual(system_group_permissions, role_permissions)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["profile_id"], self.profile.id)
        self.assertEqual(receipt["seed_key"], "pitch-demo-v1")
        self.assertEqual(len(receipt["staff"]), 2)
        self.assertTrue(all(member["user_id"] for member in receipt["staff"]))

    def test_refuses_without_gate_or_with_wrong_profile_name(self):
        with self.assertRaises(CommandError):
            call_command(
                "seed_hosperator_demo_staff",
                profile_id=self.profile.id,
                expected_profile_name=self.profile.name,
                manifest=self.manifest_path,
                apply=True,
            )
        with patch.dict(os.environ, {"HOSPERATOR_ALLOW_SYNTHETIC_DEMO_DATA": "true"}):
            with self.assertRaises(CommandError):
                call_command(
                    "seed_hosperator_demo_staff",
                    profile_id=self.profile.id,
                    expected_profile_name="Wrong workspace",
                    manifest=self.manifest_path,
                    apply=True,
                )
