from __future__ import annotations

from typing import Iterable

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyInvitation, CompanyMembership, CompanyProfile, StaffGroup, StaffRole, StaffRoleAssignment
from subapps.kafka.producers.platform_events import publish_audit_fact, publish_workspace_notification


def _string(value) -> str:
    return str(value or "").strip()


def user_display_name(user: User | None) -> str:
    if user is None:
        return ""
    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = (get_full_name() or "").strip()
    elif isinstance(get_full_name, str):
        full_name = get_full_name.strip()
    if full_name:
        return full_name
    fallback = " ".join(
        part for part in [_string(getattr(user, "first_name", "")), _string(getattr(user, "last_name", ""))] if part
    ).strip()
    return fallback or _string(getattr(user, "email", "")) or f"User {getattr(user, 'id', '')}"


def _user_label(user: User | None) -> str:
    return user_display_name(user)


def _profile_label(profile: CompanyProfile) -> str:
    return _string(profile.name) or _string(profile.company_code) or str(profile.id)


def _permission_codes(items: Iterable) -> list[str]:
    return sorted({_string(getattr(item, "codename", item)) for item in items if _string(getattr(item, "codename", item))})


def _group_names(items: Iterable) -> list[str]:
    return sorted({_string(getattr(item, "name", item)) for item in items if _string(getattr(item, "name", item))})


def _user_notification_snapshot(user: User | None) -> dict[str, str]:
    if user is None:
        return {}
    return {
        "user_id": _string(getattr(user, "id", "")),
        "user_email": _string(getattr(user, "email", "")),
        "user_name": _user_label(user),
    }


def _group_recipient_snapshots(group: StaffGroup) -> list[dict[str, str]]:
    return [
        _user_notification_snapshot(user)
        for user in group.users.filter(is_active=True).distinct()
        if _string(getattr(user, "id", ""))
    ]


def _role_recipient_snapshots(role: StaffRole) -> list[dict[str, str]]:
    return [
        _user_notification_snapshot(assignment.user)
        for assignment in role.assignments.select_related("user").filter(is_active=True, user__is_active=True).distinct()
        if assignment.user_id
    ]


def _role_permissions_recipients(role: StaffRole) -> list[str]:
    return list(
        role.assignments.filter(is_active=True, user__is_active=True)
        .values_list("user_id", flat=True)
        .distinct()
    )


def _group_recipients(group: StaffGroup) -> list[str]:
    return list(group.users.filter(is_active=True).values_list("id", flat=True).distinct())


def _membership_permissions(membership: CompanyMembership) -> list[str]:
    return sorted(
        {
            _string(codename)
            for codename in membership.custom_permissions.values_list("codename", flat=True)
            if _string(codename)
        }
    )


def publish_membership_permissions_updated(
    *,
    actor: dict,
    membership: CompanyMembership,
    before_permissions: list[str],
    after_permissions: list[str],
) -> None:
    payload = {
        "profile_id": str(membership.profile_id),
        "membership_id": str(membership.id),
        "user_id": str(membership.user_id),
        "user_email": membership.user.email,
        "user_name": _user_label(membership.user),
        "role": membership.role,
        "before_permissions": before_permissions,
        "after_permissions": after_permissions,
    }
    publish_audit_fact(
        event_name="identity.membership.permissions.updated",
        payload=payload,
        workspace_id=str(membership.profile_id),
        actor=actor,
        target={"type": "membership", "id": str(membership.id), "label": _user_label(membership.user)},
        summary=f"Workspace membership permissions updated for {_user_label(membership.user)}.",
        metadata={"workspace_name": _profile_label(membership.profile)},
        changes={"permissions": {"before": before_permissions, "after": after_permissions}},
        reference_number=_string(membership.profile.company_code),
        key=f"{membership.profile_id}:{membership.id}:membership-permissions",
    )
    publish_workspace_notification(
        event_name="notification.identity.membership.permissions.updated",
        workspace_id=str(membership.profile_id),
        category="security",
        title="Your workspace access changed",
        message=f"Your workspace membership permissions were updated in {_profile_label(membership.profile)}.",
        metadata=payload,
        action_url="/notifications",
        user_ids=[str(membership.user_id)],
        key=f"{membership.profile_id}:{membership.id}:membership-permissions",
    )


def publish_membership_changed(
    *,
    actor: dict,
    membership: CompanyMembership,
    event_name: str,
    summary: str,
    severity: str = "info",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    payload = {
        "profile_id": str(membership.profile_id),
        "membership_id": str(membership.id),
        "user_id": str(membership.user_id),
        "user_email": membership.user.email,
        "user_name": _user_label(membership.user),
        "role": membership.role,
        "is_active": membership.is_active,
        "permissions": _membership_permissions(membership),
        "invited_by_user_id": _string(membership.invited_by_id),
    }
    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(membership.profile_id),
        actor=actor,
        target={"type": "membership", "id": str(membership.id), "label": _user_label(membership.user)},
        summary=summary,
        severity=severity,
        metadata={"workspace_name": _profile_label(membership.profile)},
        changes={"before": before or {}, "after": after or payload},
        reference_number=_string(membership.profile.company_code),
        key=f"{membership.profile_id}:{membership.id}:{event_name}",
    )
    publish_workspace_notification(
        event_name=f"notification.{event_name}",
        workspace_id=str(membership.profile_id),
        category="security",
        title="Your workspace access changed",
        message=summary,
        metadata=payload,
        action_url="/notifications",
        user_ids=[str(membership.user_id)],
        key=f"{membership.profile_id}:{membership.id}:{event_name}",
    )


def publish_invitation_changed(
    *,
    actor: dict,
    invitation: CompanyInvitation,
    event_name: str,
    summary: str,
    severity: str = "info",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    payload = {
        "profile_id": str(invitation.profile_id),
        "invitation_id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "invitation_code": invitation.invitation_code,
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else "",
        "invited_by_user_id": _string(invitation.invited_by_id),
        "accepted_by_user_id": _string(invitation.accepted_by_id),
    }
    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(invitation.profile_id),
        actor=actor,
        target={"type": "invitation", "id": str(invitation.id), "label": invitation.email},
        summary=summary,
        severity=severity,
        metadata={"workspace_name": _profile_label(invitation.profile)},
        changes={"before": before or {}, "after": after or payload},
        reference_number=_string(invitation.profile.company_code),
        key=f"{invitation.profile_id}:{invitation.id}:{event_name}",
    )


def publish_invitation_notification(
    *,
    invitation: CompanyInvitation,
    actor: dict,
    event_name: str,
    title: str,
    message: str,
    action_url: str,
    severity: str = "info",
) -> None:
    recipient = (
        User.objects.filter(email__iexact=invitation.email, is_active=True)
        .only("id", "email", "first_name", "last_name")
        .first()
    )
    if recipient is None:
        return

    payload = {
        "profile_id": str(invitation.profile_id),
        "invitation_id": str(invitation.id),
        "invitation_code": invitation.invitation_code,
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "user_id": str(recipient.id),
        "user_email": recipient.email,
        "user_name": _user_label(recipient),
    }
    publish_workspace_notification(
        event_name=event_name,
        workspace_id=str(invitation.profile_id),
        category="workspace",
        title=title,
        message=message,
        metadata=payload,
        action_url=action_url,
        user_ids=[str(recipient.id)],
        key=f"{invitation.profile_id}:{invitation.id}:{event_name}",
    )

    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(invitation.profile_id),
        actor=actor,
        target={"type": "notification", "id": str(invitation.id), "label": invitation.email},
        summary=message,
        severity=severity,
        metadata={"workspace_name": _profile_label(invitation.profile)},
        changes={},
        reference_number=_string(invitation.profile.company_code),
        key=f"{invitation.profile_id}:{invitation.id}:{event_name}:audit",
    )


def publish_user_permissions_updated(
    *,
    profile: CompanyProfile,
    actor: dict,
    user: User,
    before_permissions: list[str],
    after_permissions: list[str],
) -> None:
    payload = {
        "profile_id": str(profile.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "user_name": _user_label(user),
        "before_permissions": before_permissions,
        "after_permissions": after_permissions,
    }
    publish_audit_fact(
        event_name="identity.user.permissions.updated",
        payload=payload,
        workspace_id=str(profile.id),
        actor=actor,
        target={"type": "user", "id": str(user.id), "label": _user_label(user)},
        summary=f"Direct permissions updated for {_user_label(user)}.",
        metadata={"workspace_name": _profile_label(profile)},
        changes={"permissions": {"before": before_permissions, "after": after_permissions}},
        reference_number=_string(profile.company_code),
        key=f"{profile.id}:{user.id}:permissions",
    )
    publish_workspace_notification(
        event_name="notification.identity.user.permissions.updated",
        workspace_id=str(profile.id),
        category="security",
        title="Your workspace access changed",
        message=f"Your direct permissions were updated in {_profile_label(profile)}.",
        metadata=payload,
        action_url="/notifications",
        user_ids=[str(user.id)],
        key=f"{profile.id}:{user.id}:permissions",
    )


def publish_user_groups_updated(
    *,
    profile: CompanyProfile,
    actor: dict,
    user: User,
    before_groups: list[str],
    after_groups: list[str],
) -> None:
    payload = {
        "profile_id": str(profile.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "user_name": _user_label(user),
        "before_groups": before_groups,
        "after_groups": after_groups,
    }
    publish_audit_fact(
        event_name="identity.user.groups.updated",
        payload=payload,
        workspace_id=str(profile.id),
        actor=actor,
        target={"type": "user", "id": str(user.id), "label": _user_label(user)},
        summary=f"Group membership updated for {_user_label(user)}.",
        metadata={"workspace_name": _profile_label(profile)},
        changes={"groups": {"before": before_groups, "after": after_groups}},
        reference_number=_string(profile.company_code),
        key=f"{profile.id}:{user.id}:groups",
    )
    publish_workspace_notification(
        event_name="notification.identity.user.groups.updated",
        workspace_id=str(profile.id),
        category="security",
        title="Your workspace access changed",
        message=f"Your staff group membership was updated in {_profile_label(profile)}.",
        metadata=payload,
        action_url="/notifications",
        user_ids=[str(user.id)],
        key=f"{profile.id}:{user.id}:groups",
    )


def publish_group_permissions_updated(
    *,
    actor: dict,
    group: StaffGroup,
    before_permissions: list[str],
    after_permissions: list[str],
) -> None:
    affected_users = _group_recipient_snapshots(group)
    payload = {
        "profile_id": str(group.profile_id),
        "group_id": str(group.id),
        "group_name": group.name,
        "before_permissions": before_permissions,
        "after_permissions": after_permissions,
        "affected_user_ids": [item["user_id"] for item in affected_users],
        "affected_users": affected_users,
    }
    publish_audit_fact(
        event_name="identity.group.permissions.updated",
        payload=payload,
        workspace_id=str(group.profile_id),
        actor=actor,
        target={"type": "staff_group", "id": str(group.id), "label": group.name},
        summary=f"Permissions updated for group {group.name}.",
        metadata={"workspace_name": _profile_label(group.profile)},
        changes={"permissions": {"before": before_permissions, "after": after_permissions}},
        reference_number=_string(group.profile.company_code),
        key=f"{group.profile_id}:{group.id}:permissions",
    )
    if payload["affected_user_ids"]:
        publish_workspace_notification(
            event_name="notification.identity.group.permissions.updated",
            workspace_id=str(group.profile_id),
            category="security",
            title="Your workspace access changed",
            message=f"Permissions for group {group.name} were updated in {_profile_label(group.profile)}.",
            metadata=payload,
            action_url="/notifications",
            user_ids=payload["affected_user_ids"],
            key=f"{group.profile_id}:{group.id}:permissions",
        )


def publish_role_permissions_updated(
    *,
    actor: dict,
    role: StaffRole,
    before_permissions: list[str],
    after_permissions: list[str],
) -> None:
    affected_users = _role_recipient_snapshots(role)
    recipients = [item["user_id"] for item in affected_users]
    payload = {
        "profile_id": str(role.profile_id),
        "role_id": str(role.id),
        "role_name": role.name,
        "before_permissions": before_permissions,
        "after_permissions": after_permissions,
        "affected_user_ids": recipients,
        "affected_users": affected_users,
    }
    publish_audit_fact(
        event_name="identity.role.permissions.updated",
        payload=payload,
        workspace_id=str(role.profile_id),
        actor=actor,
        target={"type": "staff_role", "id": str(role.id), "label": role.name},
        summary=f"Permissions updated for role {role.name}.",
        metadata={"workspace_name": _profile_label(role.profile)},
        changes={"permissions": {"before": before_permissions, "after": after_permissions}},
        reference_number=_string(role.profile.company_code),
        key=f"{role.profile_id}:{role.id}:permissions",
    )
    if recipients:
        publish_workspace_notification(
            event_name="notification.identity.role.permissions.updated",
            workspace_id=str(role.profile_id),
            category="security",
            title="Your workspace access changed",
            message=f"Permissions for role {role.name} were updated in {_profile_label(role.profile)}.",
            metadata=payload,
            action_url="/notifications",
            user_ids=recipients,
            key=f"{role.profile_id}:{role.id}:permissions",
        )


def publish_role_assignment_changed(
    *,
    actor: dict,
    assignment: StaffRoleAssignment,
    event_name: str,
    summary: str,
    severity: str = "info",
) -> None:
    user = assignment.user
    role = assignment.role
    profile = assignment.profile
    payload = {
        "profile_id": str(profile.id),
        "assignment_id": str(assignment.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "user_name": _user_label(user),
        "role_id": str(role.id),
        "role_name": role.name,
        "start_date": assignment.start_date.isoformat() if assignment.start_date else None,
        "end_date": assignment.end_date.isoformat() if assignment.end_date else None,
        "is_active": assignment.is_active,
    }
    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(profile.id),
        actor=actor,
        target={"type": "staff_role_assignment", "id": str(assignment.id), "label": f"{_user_label(user)} -> {role.name}"},
        summary=summary,
        severity=severity,
        metadata={"workspace_name": _profile_label(profile)},
        changes={"role_assignment": payload},
        reference_number=_string(profile.company_code),
        key=f"{profile.id}:{assignment.id}:{event_name}",
    )
    publish_workspace_notification(
        event_name=f"notification.{event_name}",
        workspace_id=str(profile.id),
        category="security",
        title="Your workspace access changed",
        message=summary,
        metadata=payload,
        action_url="/notifications",
        user_ids=[str(user.id)],
        key=f"{profile.id}:{assignment.id}:{event_name}",
    )


def publish_group_changed(
    *,
    actor: dict,
    group: StaffGroup,
    event_name: str,
    summary: str,
    severity: str = "info",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    payload = {
        "profile_id": str(group.profile_id),
        "group_id": str(group.id),
        "group_name": group.name,
        "description": group.description or "",
        "is_active": group.is_active,
        "affected_user_ids": _group_recipients(group),
    }
    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(group.profile_id),
        actor=actor,
        target={"type": "staff_group", "id": str(group.id), "label": group.name},
        summary=summary,
        severity=severity,
        metadata={"workspace_name": _profile_label(group.profile)},
        changes={"before": before or {}, "after": after or payload},
        reference_number=_string(group.profile.company_code),
        key=f"{group.profile_id}:{group.id}:{event_name}",
    )
    recipients = payload["affected_user_ids"]
    if recipients:
        publish_workspace_notification(
            event_name=f"notification.{event_name}",
            workspace_id=str(group.profile_id),
            category="security",
            title="Your workspace access changed",
            message=summary,
            metadata=payload,
            action_url="/notifications",
            user_ids=recipients,
            key=f"{group.profile_id}:{group.id}:{event_name}",
        )


def publish_role_changed(
    *,
    actor: dict,
    role: StaffRole,
    event_name: str,
    summary: str,
    severity: str = "info",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    payload = {
        "profile_id": str(role.profile_id),
        "role_id": str(role.id),
        "role_name": role.name,
        "description": role.description or "",
        "is_active": role.is_active,
        "affected_user_ids": _role_permissions_recipients(role),
    }
    publish_audit_fact(
        event_name=event_name,
        payload=payload,
        workspace_id=str(role.profile_id),
        actor=actor,
        target={"type": "staff_role", "id": str(role.id), "label": role.name},
        summary=summary,
        severity=severity,
        metadata={"workspace_name": _profile_label(role.profile)},
        changes={"before": before or {}, "after": after or payload},
        reference_number=_string(role.profile.company_code),
        key=f"{role.profile_id}:{role.id}:{event_name}",
    )
    recipients = payload["affected_user_ids"]
    if recipients:
        publish_workspace_notification(
            event_name=f"notification.{event_name}",
            workspace_id=str(role.profile_id),
            category="security",
            title="Your workspace access changed",
            message=summary,
            metadata=payload,
            action_url="/notifications",
            user_ids=recipients,
            key=f"{role.profile_id}:{role.id}:{event_name}",
        )


__all__ = [
    "_group_names",
    "_permission_codes",
    "publish_group_changed",
    "publish_group_permissions_updated",
    "publish_invitation_changed",
    "publish_membership_changed",
    "publish_membership_permissions_updated",
    "publish_role_assignment_changed",
    "publish_role_changed",
    "publish_role_permissions_updated",
    "publish_user_groups_updated",
    "publish_user_permissions_updated",
    "user_display_name",
]
