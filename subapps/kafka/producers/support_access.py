from __future__ import annotations

from typing import Any

from mainapps.profile.models import SupportAccessGrant
from subapps.kafka.client import publish_event
from subapps.kafka.producers.platform_events import publish_workspace_notification
from subapps.kafka.topics import SUPPORT_ACCESS_EVENTS_TOPIC
from subapps.utils.request_context import frontend_origin_from_request, get_request_claim, get_request_user_id


def _string(value: Any) -> str:
    return str(value or "").strip()


def _user_name(user) -> str:
    if user is None:
        return ""
    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = (get_full_name() or "").strip()
    elif isinstance(get_full_name, str):
        full_name = get_full_name.strip()
    if not full_name:
        full_name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part).strip()
    return full_name or _string(getattr(user, "email", ""))


def build_actor(*, request=None, user=None, role: str | None = None) -> dict[str, Any]:
    request_payload = getattr(getattr(request, "auth", None), "payload", {}) if request is not None else {}
    if not isinstance(request_payload, dict):
        request_payload = {}
    resolved_user = user or getattr(request, "user", None)
    return {
        "user_id": _string(getattr(resolved_user, "id", None) or get_request_user_id(request) if request is not None else ""),
        "email": _string(getattr(resolved_user, "email", None) or request_payload.get("email")),
        "name": _user_name(resolved_user) or _string(request_payload.get("full_name") or request_payload.get("name")),
        "role": role or _string(request_payload.get("membership_role")),
        "frontend_origin": frontend_origin_from_request(request) if request is not None else "",
    }


def serialize_support_access_grant(grant: SupportAccessGrant) -> dict[str, Any]:
    profile = grant.profile
    grantee_user = grant.grantee_user
    custom_permissions = list(grant.custom_permissions.values_list("codename", flat=True))
    return {
        "workspace_id": str(grant.profile_id),
        "profile_id": str(grant.profile_id),
        "support_access_grant_id": str(grant.id),
        "profile": {
            "profile_id": str(profile.id),
            "display_name": profile.name or profile.company_code or str(profile.id),
            "company_code": profile.company_code or "",
            "owner_user_id": _string(profile.owner_id),
        },
        "grant": {
            "id": str(grant.id),
            "status": grant.current_status,
            "reason": grant.reason,
            "ticket_reference": grant.ticket_reference or "",
            "permission_mode": grant.permission_mode,
            "membership_role": grant.membership_role,
            "custom_permissions": custom_permissions,
            "effective_permissions": grant.effective_permission_codenames(),
            "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
            "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
            "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
            "responded_at": grant.responded_at.isoformat() if grant.responded_at else None,
            "last_used_at": grant.last_used_at.isoformat() if grant.last_used_at else None,
            "notes": grant.notes or "",
            "invitation_code": grant.invitation_code or "",
        },
        "grantee_user_id": _string(getattr(grantee_user, "id", "")),
        "grantee_email": getattr(grantee_user, "email", "") or grant.grantee_email_snapshot,
        "grantee_name": _user_name(grantee_user),
        "created_by_user_id": _string(grant.created_by_id),
        "approved_by_user_id": _string(grant.approved_by_id),
        "accepted_by_user_id": _string(grant.accepted_by_id),
        "revoked_by_user_id": _string(grant.revoked_by_id),
        "reason": grant.reason,
        "ticket_reference": grant.ticket_reference or "",
        "permission_mode": grant.permission_mode,
        "membership_role": grant.membership_role,
        "custom_permissions": custom_permissions,
        "effective_permissions": grant.effective_permission_codenames(),
        "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "responded_at": grant.responded_at.isoformat() if grant.responded_at else None,
        "last_used_at": grant.last_used_at.isoformat() if grant.last_used_at else None,
        "status": grant.current_status,
        "notes": grant.notes or "",
        "invitation_code": grant.invitation_code or "",
    }


def _publish_support_access_event(
    event_name: str,
    *,
    grant: SupportAccessGrant,
    actor: dict[str, Any] | None,
    title: str,
    message: str,
    severity: str = "info",
) -> dict[str, Any]:
    payload = serialize_support_access_grant(grant)
    payload.update(
        {
            "title": title,
            "message": message,
            "summary": message,
        }
    )
    metadata = {
        "permission_mode": grant.permission_mode,
        "membership_role": grant.membership_role,
        "effective_permissions": grant.effective_permission_codenames(),
    }
    return publish_event(
        SUPPORT_ACCESS_EVENTS_TOPIC,
        event_name,
        payload,
        key=str(grant.id),
        envelope_overrides={
            "workspace_id": str(grant.profile_id),
            "actor": actor or {},
            "target": {
                "type": "support_access_grant",
                "id": str(grant.id),
                "label": grant.profile.name or grant.profile.company_code or str(grant.profile_id),
                "reference_number": grant.ticket_reference or "",
            },
            "summary": message,
            "severity": severity,
            "visibility_scope": "workspace",
            "metadata": metadata,
            "reference_number": grant.ticket_reference or "",
        },
    )


def publish_support_access_grant_created(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _publish_support_access_event(
        "support_access.grant.created",
        grant=grant,
        actor=actor,
        title="Temporary support access created",
        message=f"Temporary support access was created for {grant.grantee_email_snapshot}.",
    )
    publish_workspace_notification(
        event_name="notification.support_access.grant.created",
        workspace_id=str(grant.profile_id),
        category="support_access",
        title="Temporary support access created",
        message=f"{grant.grantee_email_snapshot} can access this workspace until {grant.expires_at.isoformat()}.",
        metadata=serialize_support_access_grant(grant),
        actor=actor,
        key=str(grant.id),
    )
    return payload


def publish_support_access_grant_activated(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.grant.activated",
        grant=grant,
        actor=actor,
        title="Temporary support access activated",
        message=f"Temporary support access is active for {grant.grantee_email_snapshot}.",
    )


def publish_support_access_grant_declined(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.grant.declined",
        grant=grant,
        actor=actor,
        title="Temporary support access declined",
        message=f"Temporary support access for {grant.grantee_email_snapshot} was declined.",
        severity="warning",
    )


def publish_support_access_grant_extended(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.grant.extended",
        grant=grant,
        actor=actor,
        title="Temporary support access extended",
        message=f"Temporary support access for {grant.grantee_email_snapshot} now expires at {grant.expires_at.isoformat()}.",
    )


def publish_support_access_grant_revoked(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _publish_support_access_event(
        "support_access.grant.revoked",
        grant=grant,
        actor=actor,
        title="Temporary support access revoked",
        message=f"Temporary support access for {grant.grantee_email_snapshot} was revoked.",
        severity="warning",
    )
    publish_workspace_notification(
        event_name="notification.support_access.grant.revoked",
        workspace_id=str(grant.profile_id),
        category="support_access",
        title="Temporary support access revoked",
        message=f"{grant.grantee_email_snapshot} no longer has temporary workspace access.",
        metadata=serialize_support_access_grant(grant),
        actor=actor,
        key=str(grant.id),
    )
    return payload


def publish_support_access_grant_expired(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.grant.expired",
        grant=grant,
        actor=actor,
        title="Temporary support access expired",
        message=f"Temporary support access for {grant.grantee_email_snapshot} expired.",
        severity="warning",
    )


def publish_support_access_workspace_entered(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.workspace.entered",
        grant=grant,
        actor=actor,
        title="Support session started",
        message=f"{grant.grantee_email_snapshot} entered the workspace using temporary support access.",
    )


def publish_support_access_workspace_exited(grant: SupportAccessGrant, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    return _publish_support_access_event(
        "support_access.workspace.exited",
        grant=grant,
        actor=actor,
        title="Support session ended",
        message=f"{grant.grantee_email_snapshot} exited the workspace support session.",
    )
