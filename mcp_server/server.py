from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
from django.apps import apps
from django.db import close_old_connections
from asgiref.sync import sync_to_async

if not apps.ready:
    django.setup()

from django.db.models import Count, Prefetch, Q
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import UntypedToken
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyInvitation, CompanyMembership, CompanyProfile, StaffGroup, StaffRoleAssignment
from mainapps.profile import payloads as profile_payloads
from mainapps.profile.views import CompanyInvitationViewSet, CompanyProfileViewSet, StaffGroupViewSet, StaffRoleViewSet
from subapps.utils.request_context import coerce_identity_id

logger = logging.getLogger(__name__)


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


def _payload_to_data(value: BaseModel | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value


@dataclass(slots=True)
class UsersMcpPrincipal:
    token: str
    claims: dict[str, Any]
    user_id: str
    profile_id: int
    company_code: str | None
    permissions: set[str]


_principal_var: ContextVar[UsersMcpPrincipal | None] = ContextVar("users_mcp_principal", default=None)


def get_current_principal(*, required: bool = False) -> UsersMcpPrincipal | None:
    principal = _principal_var.get()
    if principal is None and required:
        raise RuntimeError("This MCP tool requires a valid bearer token with a profile_id claim.")
    return principal


def _build_principal_from_token(token: str) -> UsersMcpPrincipal:
    claims = dict(UntypedToken(token).payload)
    user_id = claims.get("user_id") or claims.get("id") or claims.get("sub")
    if user_id in (None, ""):
        raise RuntimeError("Access token missing user identifier.")
    profile_id = coerce_identity_id(claims.get("profile_id"))
    if profile_id is None:
        raise RuntimeError("Access token missing profile_id claim.")
    permissions = claims.get("permissions") or []
    if not isinstance(permissions, list):
        permissions = list(permissions)
    return UsersMcpPrincipal(
        token=token,
        claims=claims,
        user_id=str(user_id),
        profile_id=profile_id,
        company_code=(str(claims["company_code"]).strip() if claims.get("company_code") else None),
        permissions={str(item) for item in permissions if str(item).strip()},
    )


class UsersMcpAuthMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_header = headers.get("authorization")
        if not auth_header:
            await self.app(scope, receive, send)
            return

        token = _extract_bearer_token(auth_header)
        if token is None:
            response = JSONResponse({"detail": "Invalid Authorization header."}, status_code=401)
            await response(scope, receive, send)
            return

        try:
            principal = _build_principal_from_token(token)
        except Exception as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=401)
            await response(scope, receive, send)
            return

        reset_token = _principal_var.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            _principal_var.reset(reset_token)


def _address_payload(address: Any) -> dict[str, Any] | None:
    if address is None:
        return None
    return {
        "country": address.country or "",
        "region": address.region or "",
        "subregion": address.subregion or "",
        "city": address.city or "",
        "street": address.street or "",
        "street_number": address.street_number,
        "apt_number": address.apt_number,
        "postal_code": address.postal_code or "",
    }


def _company_profile_payload(profile: CompanyProfile, *, principal_user_id: int) -> dict[str, Any]:
    agent_configured = False
    agent_cache = getattr(profile._state, "fields_cache", {}).get("agent")
    if agent_cache is not None:
        agent_configured = True
    elif getattr(profile, "pk", None):
        try:
            agent_configured = getattr(profile, "agent", None) is not None
        except Exception:
            agent_configured = False

    membership = next(
        (item for item in getattr(profile, "active_memberships_for_mcp", []) if item.user_id == principal_user_id),
        None,
    )
    is_owner = profile.owner_id == principal_user_id
    workspace_role = CompanyMembership.MembershipRole.OWNER if is_owner else getattr(membership, "role", None)
    return {
        "id": str(profile.id),
        "company_code": profile.company_code,
        "name": profile.name,
        "industry": profile.industry or "",
        "description": profile.description or "",
        "phone": profile.phone or "",
        "email": profile.email or "",
        "website": profile.website or "",
        "currency": profile.currency or "",
        "is_verified": profile.is_verified,
        "workspace_role": workspace_role,
        "is_owner": is_owner,
        "owner_user_id": str(profile.owner_id) if profile.owner_id else None,
        "member_count": int(getattr(profile, "active_member_count", 0)),
        "role_count": int(getattr(profile, "active_role_count", 0)),
        "group_count": int(getattr(profile, "active_group_count", 0)),
        "agent_configured": agent_configured,
        "headquarters_address": _address_payload(profile.headquarters_address),
    }


def _staff_payload(user: User, *, active_profile_id: int) -> dict[str, Any]:
    membership = next(
        (item for item in getattr(user, "profile_memberships_for_mcp", []) if item.profile_id == active_profile_id),
        None,
    )
    role_names = sorted(
        {
            assignment.role.name
            for assignment in getattr(user, "active_role_assignments_for_mcp", [])
            if assignment.role_id
        }
    )
    group_names = sorted({group.name for group in getattr(user, "active_staff_groups_for_mcp", [])})
    return {
        "id": str(user.id),
        "full_name": user.get_full_name,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "email": user.email,
        "phone": user.phone or "",
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "workspace_role": getattr(membership, "role", None),
        "staff_roles": role_names,
        "staff_groups": group_names,
    }


def _invitation_payload(invitation: CompanyInvitation) -> dict[str, Any]:
    profile = getattr(invitation._state, "fields_cache", {}).get("profile")
    invited_by = getattr(invitation._state, "fields_cache", {}).get("invited_by")
    accepted_by = getattr(invitation._state, "fields_cache", {}).get("accepted_by")
    return {
        "id": str(invitation.id),
        "invitation_code": invitation.invitation_code,
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "profile_id": str(invitation.profile_id),
        "profile_name": profile.name if profile is not None else "",
        "company_code": profile.company_code if profile is not None else "",
        "invited_by_user_id": str(invitation.invited_by_id) if invitation.invited_by_id else None,
        "invited_by_email": invited_by.email if invited_by is not None else "",
        "accepted_by_user_id": str(invitation.accepted_by_id) if invitation.accepted_by_id else None,
        "accepted_by_email": accepted_by.email if accepted_by is not None else "",
        "invitation_message": invitation.invitation_message or "",
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        "responded_at": invitation.responded_at.isoformat() if invitation.responded_at else None,
        "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
    }


def _accessible_profile_queryset(*, principal: UsersMcpPrincipal):
    principal_user_id = coerce_identity_id(principal.user_id)
    return (
        CompanyProfile.objects.select_related("owner", "headquarters_address", "agent")
        .prefetch_related(
            Prefetch(
                "memberships",
                queryset=CompanyMembership.objects.filter(is_active=True),
                to_attr="active_memberships_for_mcp",
            )
        )
        .annotate(
            active_member_count=Count("memberships", filter=Q(memberships__is_active=True), distinct=True),
            active_role_count=Count("staffrole_set", filter=Q(staffrole_set__is_active=True), distinct=True),
            active_group_count=Count("staffgroup_set", filter=Q(staffgroup_set__is_active=True), distinct=True),
        )
        .filter(
            Q(owner_id=principal_user_id)
            | Q(memberships__user_id=principal_user_id, memberships__is_active=True)
        )
        .distinct()
        .order_by("name", "id")
    )


def _list_accessible_company_profiles_sync(
    *,
    principal: UsersMcpPrincipal,
    query: str | None,
    limit: int,
) -> dict[str, Any]:
    principal_user_id = coerce_identity_id(principal.user_id)
    queryset = _accessible_profile_queryset(principal=principal)
    term = str(query or "").strip()
    if term:
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(company_code__icontains=term)
            | Q(email__icontains=term)
            | Q(phone__icontains=term)
            | Q(description__icontains=term)
        )

    profiles = list(queryset[:limit])
    return {
        "query": term or None,
        "count": len(profiles),
        "limit": limit,
        "active_profile_id": principal.profile_id,
        "results": [
            _company_profile_payload(profile, principal_user_id=principal_user_id or 0) for profile in profiles
        ],
    }


def _get_active_company_profile_sync(*, principal: UsersMcpPrincipal) -> dict[str, Any]:
    principal_user_id = coerce_identity_id(principal.user_id)
    profile = _accessible_profile_queryset(principal=principal).filter(id=principal.profile_id).first()
    if profile is None:
        raise RuntimeError("Authenticated profile_id is not accessible to the caller.")

    return {
        "profile": _company_profile_payload(profile, principal_user_id=principal_user_id or 0),
        "profile_id": principal.profile_id,
        "company_code": principal.company_code,
    }


def _search_company_staff_sync(
    *,
    principal: UsersMcpPrincipal,
    query: str | None,
    limit: int,
    include_inactive: bool,
) -> dict[str, Any]:
    active_profile = _accessible_profile_queryset(principal=principal).filter(id=principal.profile_id).first()
    if active_profile is None:
        raise RuntimeError("Authenticated profile_id is not accessible to the caller.")

    profile_id = principal.profile_id
    queryset = (
        User.objects.filter(
            Q(profile_id=profile_id) | Q(company_memberships__profile_id=profile_id, company_memberships__is_active=True)
        )
        .prefetch_related(
            Prefetch(
                "roles",
                queryset=StaffRoleAssignment.objects.filter(is_active=True, role__profile_id=profile_id).select_related("role"),
                to_attr="active_role_assignments_for_mcp",
            ),
            Prefetch(
                "staff_groups",
                queryset=StaffGroup.objects.filter(profile_id=profile_id, is_active=True).order_by("name"),
                to_attr="active_staff_groups_for_mcp",
            ),
            Prefetch(
                "company_memberships",
                queryset=CompanyMembership.objects.filter(profile_id=profile_id, is_active=True),
                to_attr="profile_memberships_for_mcp",
            ),
        )
        .distinct()
        .order_by("first_name", "last_name", "email")
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)

    term = str(query or "").strip()
    if term:
        queryset = queryset.filter(
            Q(email__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(phone__icontains=term)
        )

    users = list(queryset[:limit])
    return {
        "query": term or None,
        "count": len(users),
        "limit": limit,
        "profile_id": profile_id,
        "results": [_staff_payload(user, active_profile_id=profile_id) for user in users],
    }


def _staff_queryset_for_profile(*, profile_id: int):
    return (
        User.objects.filter(
            Q(profile_id=profile_id) | Q(company_memberships__profile_id=profile_id, company_memberships__is_active=True)
        )
        .prefetch_related(
            Prefetch(
                "roles",
                queryset=StaffRoleAssignment.objects.filter(is_active=True, role__profile_id=profile_id)
                .select_related("role")
                .prefetch_related("role__permissions"),
                to_attr="active_role_assignments_for_mcp_detail",
            ),
            Prefetch(
                "staff_groups",
                queryset=StaffGroup.objects.filter(profile_id=profile_id, is_active=True).prefetch_related("permissions"),
                to_attr="active_staff_groups_for_mcp_detail",
            ),
            Prefetch(
                "company_memberships",
                queryset=CompanyMembership.objects.filter(profile_id=profile_id, is_active=True).prefetch_related(
                    "custom_permissions"
                ),
                to_attr="profile_memberships_for_mcp_detail",
            ),
        )
        .distinct()
    )


def _get_staff_profile_sync(
    *,
    principal: UsersMcpPrincipal,
    user_id: str,
) -> dict[str, Any]:
    active_profile = _accessible_profile_queryset(principal=principal).filter(id=principal.profile_id).first()
    if active_profile is None:
        raise RuntimeError("Authenticated profile_id is not accessible to the caller.")

    target_user = _staff_queryset_for_profile(profile_id=principal.profile_id).filter(id=user_id).first()
    if target_user is None:
        raise ValueError("User not found.")

    membership = next(
        (item for item in getattr(target_user, "profile_memberships_for_mcp_detail", []) if item.profile_id == principal.profile_id),
        None,
    )
    role_assignments = getattr(target_user, "active_role_assignments_for_mcp_detail", [])
    groups = getattr(target_user, "active_staff_groups_for_mcp_detail", [])
    custom_permissions = sorted(
        permission.codename for permission in (membership.custom_permissions.all() if membership else [])
    )

    return {
        "profile_id": principal.profile_id,
        "staff": _staff_payload(target_user, active_profile_id=principal.profile_id),
        "membership": {
            "profile_id": str(principal.profile_id),
            "workspace_role": getattr(membership, "role", None),
            "joined_at": membership.created_at.isoformat() if membership and membership.created_at else None,
            "custom_permissions": custom_permissions,
        },
        "roles": [
            {
                "id": str(assignment.role_id),
                "name": assignment.role.name,
                "permissions": sorted(permission.codename for permission in assignment.role.permissions.all()),
            }
            for assignment in role_assignments
            if assignment.role_id
        ],
        "groups": [
            {
                "id": str(group.id),
                "name": group.name,
                "permissions": sorted(permission.codename for permission in group.permissions.all()),
            }
            for group in groups
        ],
    }


def _get_role_assignments_sync(
    *,
    principal: UsersMcpPrincipal,
    user_id: str,
) -> dict[str, Any]:
    profile = _accessible_profile_queryset(principal=principal).filter(id=principal.profile_id).first()
    if profile is None:
        raise RuntimeError("Authenticated profile_id is not accessible to the caller.")

    target_user = _staff_queryset_for_profile(profile_id=principal.profile_id).filter(id=user_id).first()
    if target_user is None:
        raise ValueError("User not found.")

    role_assignments = getattr(target_user, "active_role_assignments_for_mcp_detail", [])
    groups = getattr(target_user, "active_staff_groups_for_mcp_detail", [])

    role_rows = [
        {
            "role_id": str(assignment.role_id),
            "role_name": assignment.role.name,
            "permissions": sorted(permission.codename for permission in assignment.role.permissions.all()),
        }
        for assignment in role_assignments
        if assignment.role_id
    ]
    group_rows = [
        {
            "group_id": str(group.id),
            "group_name": group.name,
            "permissions": sorted(permission.codename for permission in group.permissions.all()),
        }
        for group in groups
    ]
    effective_permissions = sorted(
        {
            permission
            for row in [*role_rows, *group_rows]
            for permission in row["permissions"]
        }
    )
    return {
        "profile_id": principal.profile_id,
        "user_id": str(target_user.id),
        "email": target_user.email,
        "role_assignments": role_rows,
        "group_assignments": group_rows,
        "effective_permissions": effective_permissions,
    }


def _list_pending_company_invitations_sync(
    *,
    principal: UsersMcpPrincipal,
    query: str | None,
    limit: int,
) -> dict[str, Any]:
    queryset = (
        CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by")
        .filter(profile_id=principal.profile_id, status=CompanyInvitation.InvitationStatus.PENDING)
        .order_by("-created_at", "-id")
    )
    term = str(query or "").strip()
    if term:
        queryset = queryset.filter(
            Q(email__icontains=term)
            | Q(profile__name__icontains=term)
            | Q(invitation_code__icontains=term)
            | Q(invited_by__email__icontains=term)
        )
    invitations = list(queryset[:limit])
    return {
        "profile_id": principal.profile_id,
        "query": term or None,
        "count": len(invitations),
        "results": [_invitation_payload(invitation) for invitation in invitations],
    }


def _list_my_company_invitations_sync(
    *,
    principal: UsersMcpPrincipal,
    status: str | None,
    limit: int,
) -> dict[str, Any]:
    queryset = (
        CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by")
        .filter(email__iexact=str(principal.claims.get("email") or "").strip())
        .order_by("-created_at", "-id")
    )
    if status:
        queryset = queryset.filter(status=status)
    invitations = list(queryset[:limit])
    return {
        "profile_id": principal.profile_id,
        "email": str(principal.claims.get("email") or "").strip() or None,
        "status": status,
        "count": len(invitations),
        "results": [_invitation_payload(invitation) for invitation in invitations],
    }


def _get_company_invitation_sync(
    *,
    principal: UsersMcpPrincipal,
    invitation_code: str,
) -> dict[str, Any]:
    invitation = (
        CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by")
        .filter(invitation_code=invitation_code)
        .first()
    )
    if invitation is None:
        raise ValueError("Invitation not found.")
    return {
        "profile_id": principal.profile_id,
        "invitation": _invitation_payload(invitation),
    }


def _resend_company_invitation_sync(
    *,
    principal: UsersMcpPrincipal,
    invitation_id: str,
) -> dict[str, Any]:
    close_old_connections()
    factory = APIRequestFactory()
    request = factory.post(
        "/mcp/internal",
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {principal.token}",
        HTTP_HOST="localhost",
    )
    view = CompanyInvitationViewSet.as_view({"post": "resend"})
    try:
        response = view(request, pk=invitation_id)
    finally:
        close_old_connections()
    status_code = getattr(response, "status_code", 200)
    payload = getattr(response, "data", None)
    if status_code >= 400:
        raise ValueError(str(payload or {"detail": "Request failed."}))
    return {
        "profile_id": principal.profile_id,
        "result": payload,
    }


def _invoke_view_action_sync(
    *,
    principal: UsersMcpPrincipal,
    viewset_cls,
    action: str,
    method: str,
    pk: str | None = None,
    data: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
) -> Any:
    close_old_connections()
    factory = APIRequestFactory()
    http_method = method.lower().strip()
    path = "/mcp/internal"
    request_headers = {
        "HTTP_AUTHORIZATION": f"Bearer {principal.token}",
        "HTTP_HOST": "localhost",
    }

    if http_method == "get":
        request = factory.get(path, data=query_params or {}, format="json", **request_headers)
    elif http_method == "post":
        request = factory.post(path, data=data or {}, format="json", **request_headers)
    elif http_method == "patch":
        request = factory.patch(path, data=data or {}, format="json", **request_headers)
    elif http_method == "put":
        request = factory.put(path, data=data or {}, format="json", **request_headers)
    elif http_method == "delete":
        request = factory.delete(path, data=data or {}, format="json", **request_headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    view = viewset_cls.as_view({http_method: action})
    try:
        response = view(request, pk=pk) if pk is not None else view(request)
    finally:
        close_old_connections()
    status_code = getattr(response, "status_code", 200)
    payload = getattr(response, "data", None)
    if status_code >= 400:
        raise ValueError(str(payload or {"detail": "Request failed."}))
    return payload


def _invite_company_staff_sync(*, principal: UsersMcpPrincipal, data: dict[str, Any]) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyInvitationViewSet,
        action="invite",
        method="post",
        data=data,
    )
    return {"profile_id": principal.profile_id, "invitation": payload}


def _invite_company_staff_bulk_sync(*, principal: UsersMcpPrincipal, data: dict[str, Any]) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyInvitationViewSet,
        action="invite_bulk",
        method="post",
        data=data,
    )
    return {"profile_id": principal.profile_id, "result": payload}


def _revoke_company_invitation_sync(
    *,
    principal: UsersMcpPrincipal,
    invitation_id: str,
) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyInvitationViewSet,
        action="revoke",
        method="post",
        pk=invitation_id,
    )
    return {"profile_id": principal.profile_id, "result": payload}


def _accept_company_invitation_sync(*, principal: UsersMcpPrincipal, data: dict[str, Any]) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyInvitationViewSet,
        action="accept",
        method="post",
        data=data,
    )
    return {"profile_id": principal.profile_id, "result": payload}


def _decline_company_invitation_sync(*, principal: UsersMcpPrincipal, data: dict[str, Any]) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyInvitationViewSet,
        action="decline",
        method="post",
        data=data,
    )
    return {"profile_id": principal.profile_id, "result": payload}


def _remove_company_staff_sync(*, principal: UsersMcpPrincipal, profile_id: str, data: dict[str, Any]) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyProfileViewSet,
        action="remove_staff",
        method="post",
        pk=profile_id,
        data=data,
    )
    return {"profile_id": principal.profile_id, "result": payload}


def _list_company_roles_sync(*, principal: UsersMcpPrincipal, profile_id: str) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyProfileViewSet,
        action="roles",
        method="get",
        pk=profile_id,
    )
    return {"profile_id": principal.profile_id, "results": payload}


def _list_company_groups_sync(*, principal: UsersMcpPrincipal, profile_id: str) -> dict[str, Any]:
    payload = _invoke_view_action_sync(
        principal=principal,
        viewset_cls=CompanyProfileViewSet,
        action="groups",
        method="get",
        pk=profile_id,
    )
    return {"profile_id": principal.profile_id, "results": payload}


def _get_staff_permissions_summary_sync(
    *,
    principal: UsersMcpPrincipal,
    user_id: str,
) -> dict[str, Any]:
    active_profile = _accessible_profile_queryset(principal=principal).filter(id=principal.profile_id).first()
    if active_profile is None:
        raise RuntimeError("Authenticated profile_id is not accessible to the caller.")

    target_user = (
        User.objects.prefetch_related(
            Prefetch(
                "roles",
                queryset=StaffRoleAssignment.objects.filter(
                    is_active=True,
                    role__profile_id=principal.profile_id,
                ).select_related("role").prefetch_related("role__permissions"),
                to_attr="active_role_assignments_for_mcp_summary",
            ),
            Prefetch(
                "staff_groups",
                queryset=StaffGroup.objects.filter(profile_id=principal.profile_id, is_active=True).prefetch_related("permissions"),
                to_attr="active_staff_groups_for_mcp_summary",
            ),
            Prefetch(
                "company_memberships",
                queryset=CompanyMembership.objects.filter(profile_id=principal.profile_id, is_active=True).prefetch_related("custom_permissions"),
                to_attr="profile_memberships_for_mcp_summary",
            ),
        )
        .filter(id=user_id)
        .first()
    )
    if target_user is None:
        raise ValueError("User not found.")

    membership = next(
        (item for item in getattr(target_user, "profile_memberships_for_mcp_summary", []) if item.profile_id == principal.profile_id),
        None,
    )
    role_assignments = getattr(target_user, "active_role_assignments_for_mcp_summary", [])
    groups = getattr(target_user, "active_staff_groups_for_mcp_summary", [])

    role_permissions = sorted(
        {
            permission.codename
            for assignment in role_assignments
            for permission in assignment.role.permissions.all()
        }
    )
    group_permissions = sorted(
        {
            permission.codename
            for group in groups
            for permission in group.permissions.all()
        }
    )
    custom_permissions = sorted(
        permission.codename for permission in (membership.custom_permissions.all() if membership else [])
    )
    effective_permissions = sorted(set(role_permissions) | set(group_permissions) | set(custom_permissions))
    return {
        "profile_id": principal.profile_id,
        "user_id": str(target_user.id),
        "email": target_user.email,
        "workspace_role": getattr(membership, "role", None),
        "roles": sorted({assignment.role.name for assignment in role_assignments if assignment.role_id}),
        "groups": sorted({group.name for group in groups}),
        "role_permissions": role_permissions,
        "group_permissions": group_permissions,
        "custom_permissions": custom_permissions,
        "effective_permissions": effective_permissions,
    }


def _build_transport_security_settings() -> TransportSecuritySettings:
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_hosts.extend(_parse_csv(os.getenv("USERS_MCP_ALLOWED_HOSTS") or os.getenv("ALLOWED_HOSTS")))

    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    allowed_origins.extend(_parse_csv(os.getenv("USERS_MCP_ALLOWED_ORIGINS") or os.getenv("CORS_ALLOWED_ORIGINS")))

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(allowed_hosts)),
        allowed_origins=list(dict.fromkeys(allowed_origins)),
    )


MCP_SERVER_NAME = os.getenv("USERS_MCP_SERVER_NAME") or "users-service-mcp"
MCP_SERVER_HOST = os.getenv("USERS_MCP_HOST") or "0.0.0.0"
MCP_SERVER_PORT = int(os.getenv("USERS_MCP_PORT") or "8000")
MCP_SERVER_LOG_LEVEL = (os.getenv("USERS_MCP_LOG_LEVEL") or "info").upper()

mcp = FastMCP(
    MCP_SERVER_NAME,
    instructions=(
        "Tools for the User and workspace service. Authenticated tools are scoped to the caller's user_id "
        "and profile_id from the forwarded User Service access token."
    ),
    host=MCP_SERVER_HOST,
    port=MCP_SERVER_PORT,
    log_level=MCP_SERVER_LOG_LEVEL,
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=_build_transport_security_settings(),
)


@mcp.tool(
    name="list_accessible_company_profiles",
    description="List company workspaces the authenticated caller can access.",
)
async def list_accessible_company_profiles(
    query: str | None = None,
    limit: int = 10,
) -> profile_payloads.CompanyProfileSearchResponsePayload:
    principal = get_current_principal(required=True)
    limit_value = max(1, min(int(limit), 25))
    return await sync_to_async(_list_accessible_company_profiles_sync, thread_sensitive=True)(
        principal=principal,
        query=query,
        limit=limit_value,
    )


@mcp.tool(
    name="get_active_company_profile",
    description="Get the active company workspace resolved from the authenticated caller's profile_id claim.",
)
async def get_active_company_profile() -> profile_payloads.ActiveCompanyProfileResponsePayload:
    try:
        principal = get_current_principal(required=True)
        return await sync_to_async(_get_active_company_profile_sync, thread_sensitive=True)(principal=principal)
    except Exception:
        logger.exception(
            "users mcp get_active_company_profile failed profile_id=%s user_id=%s",
            getattr(get_current_principal(required=False), "profile_id", None),
            getattr(get_current_principal(required=False), "user_id", None),
        )
        raise


@mcp.tool(
    name="search_company_staff",
    description="Search staff members within the authenticated caller's active company workspace.",
)
async def search_company_staff(
    query: str | None = None,
    limit: int = 10,
    include_inactive: bool = False,
) -> profile_payloads.CompanyStaffSearchResponsePayload:
    principal = get_current_principal(required=True)
    limit_value = max(1, min(int(limit), 25))
    return await sync_to_async(_search_company_staff_sync, thread_sensitive=True)(
        principal=principal,
        query=query,
        limit=limit_value,
        include_inactive=include_inactive,
    )


@mcp.tool(
    name="get_staff_profile",
    description="Get a staff member profile, membership, roles, and groups for the active company workspace.",
)
async def get_staff_profile(user_id: str) -> dict[str, Any]:
    principal = get_current_principal(required=True)
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        raise ValueError("user_id is required")
    return await sync_to_async(_get_staff_profile_sync, thread_sensitive=True)(
        principal=principal,
        user_id=target_user_id,
    )


@mcp.tool(
    name="get_role_assignments",
    description="Get role and group assignments for a staff member in the active company workspace.",
)
async def get_role_assignments(user_id: str) -> dict[str, Any]:
    principal = get_current_principal(required=True)
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        raise ValueError("user_id is required")
    return await sync_to_async(_get_role_assignments_sync, thread_sensitive=True)(
        principal=principal,
        user_id=target_user_id,
    )


@mcp.tool(
    name="list_pending_company_invitations",
    description="List pending company invitations for the active workspace.",
)
async def list_pending_company_invitations(
    query: str | None = None,
    limit: int = 10,
) -> profile_payloads.InvitationListResponsePayload:
    principal = get_current_principal(required=True)
    limit_value = max(1, min(int(limit), 50))
    return await sync_to_async(_list_pending_company_invitations_sync, thread_sensitive=True)(
        principal=principal,
        query=query,
        limit=limit_value,
    )


@mcp.tool(
    name="list_my_company_invitations",
    description="List invitations addressed to the authenticated user's email.",
)
async def list_my_company_invitations(
    status: str | None = None,
    limit: int = 10,
) -> profile_payloads.InvitationListResponsePayload:
    principal = get_current_principal(required=True)
    limit_value = max(1, min(int(limit), 50))
    return await sync_to_async(_list_my_company_invitations_sync, thread_sensitive=True)(
        principal=principal,
        status=status,
        limit=limit_value,
    )


@mcp.tool(
    name="get_company_invitation",
    description="Get a company invitation by invitation code.",
)
async def get_company_invitation(
    invitation_code: str,
) -> profile_payloads.InvitationDetailResponsePayload:
    principal = get_current_principal(required=True)
    target_code = str(invitation_code or "").strip()
    if not target_code:
        raise ValueError("invitation_code is required")
    return await sync_to_async(_get_company_invitation_sync, thread_sensitive=True)(
        principal=principal,
        invitation_code=target_code,
    )


@mcp.tool(
    name="resend_company_invitation",
    description="Resend a pending company invitation email.",
)
async def resend_company_invitation(
    invitation_id: str,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    target_id = str(invitation_id or "").strip()
    if not target_id:
        raise ValueError("invitation_id is required")
    return await sync_to_async(_resend_company_invitation_sync, thread_sensitive=True)(
        principal=principal,
        invitation_id=target_id,
    )


@mcp.tool(
    name="invite_company_staff",
    description="Invite a staff member to the active company workspace.",
)
async def invite_company_staff(
    payload: profile_payloads.InviteCompanyStaffPayload,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    if not payload:
        raise ValueError("payload is required")
    return await sync_to_async(_invite_company_staff_sync, thread_sensitive=True)(
        principal=principal,
        data=_payload_to_data(payload),
    )


@mcp.tool(
    name="invite_company_staff_bulk",
    description="Bulk invite staff members to the active company workspace.",
)
async def invite_company_staff_bulk(
    payload: profile_payloads.BulkInviteCompanyStaffPayload,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    if not payload:
        raise ValueError("payload is required")
    return await sync_to_async(_invite_company_staff_bulk_sync, thread_sensitive=True)(
        principal=principal,
        data=_payload_to_data(payload),
    )


@mcp.tool(
    name="revoke_company_invitation",
    description="Revoke a pending company invitation.",
)
async def revoke_company_invitation(
    invitation_id: str,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    target_id = str(invitation_id or "").strip()
    if not target_id:
        raise ValueError("invitation_id is required")
    return await sync_to_async(_revoke_company_invitation_sync, thread_sensitive=True)(
        principal=principal,
        invitation_id=target_id,
    )


@mcp.tool(
    name="accept_company_invitation",
    description="Accept a company invitation using the backend's canonical accept workflow.",
)
async def accept_company_invitation(
    payload: profile_payloads.InvitationDecisionPayload,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    if not payload:
        raise ValueError("payload is required")
    return await sync_to_async(_accept_company_invitation_sync, thread_sensitive=True)(
        principal=principal,
        data=_payload_to_data(payload),
    )


@mcp.tool(
    name="decline_company_invitation",
    description="Decline a company invitation using the backend's canonical decline workflow.",
)
async def decline_company_invitation(
    payload: profile_payloads.InvitationDecisionPayload,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    if not payload:
        raise ValueError("payload is required")
    return await sync_to_async(_decline_company_invitation_sync, thread_sensitive=True)(
        principal=principal,
        data=_payload_to_data(payload),
    )


@mcp.tool(
    name="remove_company_staff",
    description="Remove a staff member from a company workspace.",
)
async def remove_company_staff(
    profile_id: str | None = None,
    payload: profile_payloads.RemoveCompanyStaffPayload | None = None,
) -> profile_payloads.CompanyInvitationActionResultPayload:
    principal = get_current_principal(required=True)
    target_profile_id = str(profile_id or principal.profile_id).strip()
    if not target_profile_id:
        raise ValueError("profile_id is required")
    if not payload:
        raise ValueError("payload is required")
    return await sync_to_async(_remove_company_staff_sync, thread_sensitive=True)(
        principal=principal,
        profile_id=target_profile_id,
        data=_payload_to_data(payload),
    )


@mcp.tool(
    name="list_company_roles",
    description="List roles in the active company workspace.",
)
async def list_company_roles(
    profile_id: str | None = None,
) -> profile_payloads.CompanyRolesResponsePayload:
    principal = get_current_principal(required=True)
    target_profile_id = str(profile_id or principal.profile_id).strip()
    return await sync_to_async(_list_company_roles_sync, thread_sensitive=True)(
        principal=principal,
        profile_id=target_profile_id,
    )


@mcp.tool(
    name="list_company_groups",
    description="List groups in the active company workspace.",
)
async def list_company_groups(
    profile_id: str | None = None,
) -> profile_payloads.CompanyGroupsResponsePayload:
    principal = get_current_principal(required=True)
    target_profile_id = str(profile_id or principal.profile_id).strip()
    return await sync_to_async(_list_company_groups_sync, thread_sensitive=True)(
        principal=principal,
        profile_id=target_profile_id,
    )


@mcp.tool(
    name="get_staff_permissions_summary",
    description="Summarize a staff member's effective permissions in the active company workspace.",
)
async def get_staff_permissions_summary(
    user_id: str,
) -> profile_payloads.StaffPermissionsSummaryResponsePayload:
    principal = get_current_principal(required=True)
    target_user_id = str(user_id or "").strip()
    if not target_user_id:
        raise ValueError("user_id is required")
    return await sync_to_async(_get_staff_permissions_summary_sync, thread_sensitive=True)(
        principal=principal,
        user_id=target_user_id,
    )


async def health(_: Any) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _build_app_lifespan(mcp_app: Starlette):
    @asynccontextmanager
    async def lifespan(_: Starlette):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    return lifespan


def create_app() -> Starlette:
    mount_path = (os.getenv("USERS_MCP_MOUNT_PATH") or "/mcp").strip() or "/mcp"
    if not mount_path.startswith("/"):
        mount_path = f"/{mount_path}"
    mcp_app = mcp.streamable_http_app()
    return Starlette(
        debug=_parse_bool(os.getenv("USERS_MCP_DEBUG"), default=False),
        lifespan=_build_app_lifespan(mcp_app),
        middleware=[Middleware(UsersMcpAuthMiddleware)],
        routes=[
            Route("/health", endpoint=health),
            Mount(mount_path, app=mcp_app),
        ],
    )


app = create_app()


def main() -> None:
    uvicorn.run(
        "mcp_server.server:app",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        log_level=MCP_SERVER_LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
