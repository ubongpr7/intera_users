from __future__ import annotations

import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
from django.apps import apps
from asgiref.sync import sync_to_async

if not apps.ready:
    django.setup()

from django.db.models import Count, Prefetch, Q
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from rest_framework_simplejwt.tokens import UntypedToken
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyMembership, CompanyProfile, StaffGroup, StaffRoleAssignment
from subapps.utils.request_context import coerce_identity_id


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
async def list_accessible_company_profiles(query: str | None = None, limit: int = 10) -> dict[str, Any]:
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
async def get_active_company_profile() -> dict[str, Any]:
    principal = get_current_principal(required=True)
    return await sync_to_async(_get_active_company_profile_sync, thread_sensitive=True)(principal=principal)


@mcp.tool(
    name="search_company_staff",
    description="Search staff members within the authenticated caller's active company workspace.",
)
async def search_company_staff(
    query: str | None = None,
    limit: int = 10,
    include_inactive: bool = False,
) -> dict[str, Any]:
    principal = get_current_principal(required=True)
    limit_value = max(1, min(int(limit), 25))
    return await sync_to_async(_search_company_staff_sync, thread_sensitive=True)(
        principal=principal,
        query=query,
        limit=limit_value,
        include_inactive=include_inactive,
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
