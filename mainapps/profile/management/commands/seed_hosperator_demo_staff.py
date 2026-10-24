"""Provision silent synthetic staff identities for an isolated Hosperator demo."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import post_save

from mainapps.accounts.models import User
from mainapps.permit.models import PlatformChoices
from mainapps.profile.default_staff_presets import (
    sync_system_staff_groups,
    sync_system_staff_roles,
)
from mainapps.profile.models import (
    CompanyMembership,
    CompanyProfile,
    StaffGroup,
    StaffRole,
    StaffRoleAssignment,
)


ALLOW_ENV = "HOSPERATOR_ALLOW_SYNTHETIC_DEMO_DATA"


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_manifest(path: Path, profile_id: int) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(f"Unable to read a valid demo manifest: {error}") from error

    if manifest.get("synthetic") is not True:
        raise CommandError("The manifest must declare synthetic=true.")
    if manifest.get("external_delivery_allowed") is not False:
        raise CommandError("The manifest must disable external delivery.")
    if manifest.get("profile_id") != profile_id:
        raise CommandError("The manifest profile_id does not match --profile-id.")
    staff = manifest.get("staff")
    if not isinstance(staff, list) or not staff:
        raise CommandError("The manifest must contain at least one staff record.")

    emails = set()
    for index, member in enumerate(staff, start=1):
        if not isinstance(member, dict):
            raise CommandError(f"Staff record {index} must be an object.")
        email = str(member.get("email") or "").strip().lower()
        if not email.endswith("@example.invalid"):
            raise CommandError(f"Staff record {index} must use the reserved example.invalid domain.")
        if email in emails:
            raise CommandError(f"Duplicate staff email in manifest: {email}")
        if member.get("can_sign_in") is not False:
            raise CommandError(f"Staff record {index} must declare can_sign_in=false.")
        for required in ("first_name", "last_name", "role", "group"):
            if not str(member.get(required) or "").strip():
                raise CommandError(f"Staff record {index} is missing {required}.")
        emails.add(email)
    return manifest


@contextmanager
def _suppress_external_identity_events():
    """Keep this synthetic fixture entirely local to the shared Users database."""

    from mainapps.accounts.signals import post_save_initialize_user
    from mainapps.profile.signals import publish_company_membership

    receivers = (
        (post_save_initialize_user, User),
        (publish_company_membership, CompanyMembership),
    )
    for receiver, sender in receivers:
        post_save.disconnect(receiver, sender=sender)
    try:
        yield
    finally:
        for receiver, sender in receivers:
            post_save.connect(receiver, sender=sender)


class Command(BaseCommand):
    help = (
        "Create non-login synthetic Hosperator staff from a pitch-demo manifest. "
        "No invitation or notification is sent. The command is disabled in production."
    )

    def add_arguments(self, parser):
        parser.add_argument("--profile-id", type=int, required=True)
        parser.add_argument("--expected-profile-name", required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument(
            "--receipt",
            type=Path,
            help="Optional JSON receipt containing the stable synthetic user, role, and group IDs.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the validated synthetic identities. Without this flag the command is a dry run.",
        )

    def handle(self, *args, **options):
        with _suppress_external_identity_events():
            return self._seed(*args, **options)

    @transaction.atomic
    def _seed(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("Synthetic demo staff cannot be seeded in production.")
        if not _enabled(os.getenv(ALLOW_ENV)):
            raise CommandError(f"Set {ALLOW_ENV}=true before running this command.")

        profile_id = options["profile_id"]
        try:
            profile = CompanyProfile.objects.get(pk=profile_id)
        except CompanyProfile.DoesNotExist as error:
            raise CommandError("The target profile does not exist.") from error
        if profile.name != options["expected_profile_name"]:
            raise CommandError(
                "The target profile name does not match --expected-profile-name; refusing to continue."
            )

        manifest = _load_manifest(options["manifest"], profile_id)
        staff = manifest["staff"]
        if not options["apply"]:
            self.stdout.write(
                f"Dry run: {len(staff)} synthetic non-login staff identities are valid for "
                f"profile {profile.id} ({profile.name}); no data was written."
            )
            return

        sync_system_staff_roles(platform=PlatformChoices.HOSPERATOR)
        sync_system_staff_groups(platform=PlatformChoices.HOSPERATOR)
        roles = {
            role.name: role
            for role in StaffRole.objects.filter(
                profile__isnull=True,
                is_system=True,
                platform=PlatformChoices.HOSPERATOR,
            )
        }
        requested_roles = {str(member["role"]).strip() for member in staff}
        requested_groups = {str(member["group"]).strip() for member in staff}
        missing_roles = sorted(requested_roles - roles.keys())
        if missing_roles:
            raise CommandError(f"Unknown Hosperator role presets: {missing_roles}.")

        # Demo groups are operational labels (for example, "Front Desk"), while
        # permissions are maintained on the canonical system role presets. Copy
        # the union of the associated role permissions onto each group so group
        # listings and group-based authorization remain useful and deterministic.
        group_role_names = {group_name: set() for group_name in requested_groups}
        for member in staff:
            group_role_names[str(member["group"]).strip()].add(str(member["role"]).strip())

        groups = {}
        for group_name in requested_groups:
            groups[group_name], _ = StaffGroup.objects.get_or_create(
                profile=profile,
                platform=PlatformChoices.HOSPERATOR,
                name=group_name,
                defaults={
                    "description": "Synthetic pitch-demo staff group. Non-production use only.",
                    "is_active": True,
                    "created_by": profile.owner,
                },
            )
            permission_ids = {
                permission_id
                for role_name in group_role_names[group_name]
                for permission_id in roles[role_name].permissions.values_list("id", flat=True)
            }
            groups[group_name].permissions.set(permission_ids)

        created_count = 0
        confirmed_count = 0
        receipt_staff = []
        for member in staff:
            email = str(member["email"]).strip().lower()
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User(
                    email=email,
                    username=email,
                    first_name=str(member["first_name"]).strip(),
                    last_name=str(member["last_name"]).strip(),
                    profile=profile,
                    is_verified=True,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()
                created_count += 1
            else:
                confirmed_count += 1
                changed_fields = []
                for field in ("first_name", "last_name"):
                    value = str(member[field]).strip()
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed_fields.append(field)
                if user.has_usable_password():
                    user.set_unusable_password()
                    changed_fields.append("password")
                if not user.is_verified:
                    user.is_verified = True
                    changed_fields.append("is_verified")
                if changed_fields:
                    user.save(update_fields=changed_fields)

            CompanyMembership.objects.update_or_create(
                user=user,
                profile=profile,
                defaults={
                    "role": CompanyMembership.MembershipRole.MEMBER,
                    "is_active": True,
                    "invited_by": profile.owner,
                },
            )

            role = roles[str(member["role"]).strip()]
            StaffRoleAssignment.objects.filter(
                profile=profile,
                user=user,
                role__platform=PlatformChoices.HOSPERATOR,
                is_active=True,
            ).exclude(role=role).update(is_active=False)
            assignment = StaffRoleAssignment.objects.filter(
                profile=profile,
                user=user,
                role=role,
            ).first()
            if assignment is None or not assignment.is_active:
                if assignment is not None:
                    assignment.delete()
                StaffRoleAssignment.objects.create(
                    profile=profile,
                    user=user,
                    role=role,
                    is_active=True,
                    assigned_by=profile.owner,
                )

            target_group = groups[str(member["group"]).strip()]
            # Collapse the prior per-group remove loop into one tenant-scoped
            # through-table delete. This matters against hosted databases and
            # keeps the operation bounded to the demo groups named in the manifest.
            group_memberships = StaffGroup.users.through
            group_memberships.objects.filter(
                staffgroup__in=groups.values(),
                user_id=user.id,
            ).exclude(staffgroup_id=target_group.pk).delete()
            group_memberships.objects.get_or_create(
                staffgroup_id=target_group.pk,
                user_id=user.id,
            )
            receipt_staff.append(
                {
                    "external_ref": member.get("external_ref"),
                    "email": email,
                    "user_id": user.id,
                    "role_id": role.id,
                    "group_id": target_group.id,
                }
            )

        if options.get("receipt"):
            receipt_path = options["receipt"]
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "synthetic": True,
                        "external_delivery_allowed": False,
                        "seed_key": manifest.get("seed_key"),
                        "profile_id": profile.id,
                        "staff": receipt_staff,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Synthetic Hosperator demo staff complete for profile {profile.id}: "
                f"{created_count} created, {confirmed_count} confirmed; no email or notification sent."
            )
        )
