from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import uuid4

import jwt
from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed

from mainapps.profile.models import CompanyMembership

AUTHORIZATION_CONTEXT_HEADER = "X-Intera-Authorization-Context"
AUTHORIZATION_CONTEXT_TOKEN_TYPE = "intera_authorization_context"
WEBSOCKET_TICKET_TOKEN_TYPE = "intera_websocket_ticket"


def _setting(name: str, default=None):
    return getattr(settings, "SIMPLE_JWT", {}).get(name, default)


def _signing_key():
    return _setting("SIGNING_KEY") or settings.SECRET_KEY


def _verifying_key():
    algorithm = str(_setting("ALGORITHM", "HS256")).upper()
    if algorithm.startswith(("RS", "ES")):
        return _setting("VERIFYING_KEY")
    return _signing_key()


def _issuer():
    return getattr(settings, "JWT_ISSUER", None) or _setting("ISSUER") or "intera-users"


def _audience():
    return (
        getattr(settings, "JWT_AUDIENCE", None)
        or _setting("AUDIENCE")
        or getattr(settings, "AUTHORIZATION_CONTEXT_AUDIENCE", "intera-services")
    )


def _lifetime() -> timedelta:
    seconds = getattr(settings, "AUTHORIZATION_CONTEXT_LIFETIME_SECONDS", None)
    return timedelta(seconds=int(seconds)) if seconds is not None else _setting(
        "ACCESS_TOKEN_LIFETIME", timedelta(minutes=60)
    )


def access_context_hash(*, user_id, profile_id, session_version) -> str:
    value = json.dumps(
        {
            "profile_id": str(profile_id or ""),
            "session_version": str(session_version or ""),
            "user_id": str(user_id or ""),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _wildcard_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"system:{slug}"


def _system_access(user, profile):
    role_filter = Q(profile=profile) | Q(role__is_system=True, profile__isnull=True)
    assignments = user.roles.filter(role_filter, is_active=True).select_related("role").prefetch_related("role__permissions")
    groups = user.staff_groups.filter(
        Q(profile=profile) | Q(is_system=True, profile__isnull=True),
        is_active=True,
    ).prefetch_related("permissions")
    wildcards: set[str] = set()
    wildcard_permissions: dict[str, list[str]] = {}
    for assignment in assignments:
        if not assignment.role.is_system:
            continue
        wildcard = _wildcard_name(assignment.role.name)
        wildcards.add(wildcard)
        wildcard_permissions[wildcard] = sorted(
            set(permission.codename for permission in assignment.role.permissions.all())
        )
    for group in groups:
        if not group.is_system:
            continue
        wildcard = _wildcard_name(group.name)
        wildcards.add(wildcard)
        wildcard_permissions[wildcard] = sorted(
            set(permission.codename for permission in group.permissions.all())
        )
    return sorted(wildcards), wildcard_permissions


def issue_authorization_context(user, *, profile=None, support_grant=None) -> str:
    now = datetime.now(timezone.utc)
    direct_permissions = set(user.custom_permissions.values_list("codename", flat=True))
    if profile is not None and support_grant is None:
        membership = CompanyMembership.objects.filter(user=user, profile=profile, is_active=True).first()
        if membership:
            direct_permissions.update(
                membership.custom_permissions.values_list("codename", flat=True)
            )
    if support_grant is not None:
        direct_permissions.update(support_grant.effective_permission_codenames())
    wildcards, wildcard_permissions = _system_access(user, profile) if profile is not None else ([], {})
    payload = {
        "token_type": AUTHORIZATION_CONTEXT_TOKEN_TYPE,
        "jti": str(uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + _lifetime(),
        "iss": _issuer(),
        "aud": _audience(),
        "user_id": str(user.id),
        "profile_id": str(profile.id) if profile else None,
        "session_version": getattr(user, "session_version", None),
        "access_context_hash": access_context_hash(
            user_id=user.id,
            profile_id=profile.id if profile else None,
            session_version=getattr(user, "session_version", None),
        ),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "is_owner": bool(profile and profile.owner_id == user.id),
        "permissions": sorted(direct_permissions),
        "wildcards": wildcards,
        "wildcard_permissions": wildcard_permissions,
    }
    return jwt.encode(payload, _signing_key(), algorithm=_setting("ALGORITHM", "HS256"))


def issue_websocket_ticket(context_payload: dict) -> str:
    now = datetime.now(timezone.utc)
    lifetime = int(getattr(settings, "WEBSOCKET_TICKET_LIFETIME_SECONDS", 60))
    payload = {
        "token_type": WEBSOCKET_TICKET_TOKEN_TYPE,
        "jti": str(uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=lifetime),
        "iss": _issuer(),
        "aud": _audience(),
        "user_id": context_payload.get("user_id"),
        "profile_id": context_payload.get("profile_id"),
        "access_context_hash": context_payload.get("access_context_hash"),
        "is_staff": bool(context_payload.get("is_staff")),
        "is_owner": bool(context_payload.get("is_owner")),
        "permissions": list(context_payload.get("permissions") or []),
        "wildcards": list(context_payload.get("wildcards") or []),
        "wildcard_permissions": context_payload.get("wildcard_permissions") or {},
    }
    return jwt.encode(payload, _signing_key(), algorithm=_setting("ALGORITHM", "HS256"))


def decode_authorization_context(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            _verifying_key(),
            algorithms=[_setting("ALGORITHM", "HS256")],
            audience=_audience(),
            issuer=_issuer(),
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("Authorization context is invalid.") from exc
    if payload.get("token_type") != AUTHORIZATION_CONTEXT_TOKEN_TYPE:
        raise AuthenticationFailed("Authorization context is invalid.")
    return payload


def authorization_context_from_request(request) -> dict:
    token = request.headers.get(AUTHORIZATION_CONTEXT_HEADER)
    if not token:
        raise AuthenticationFailed("Authorization context is required.")
    payload = decode_authorization_context(token)
    access_payload = getattr(getattr(request, "auth", None), "payload", {})
    expected = access_context_hash(
        user_id=getattr(request.user, "id", None) or access_payload.get("user_id"),
        profile_id=access_payload.get("profile_id"),
        session_version=access_payload.get("session_version"),
    )
    if payload.get("access_context_hash") != expected:
        raise AuthenticationFailed("Authorization context does not match the access token.")
    return payload


def has_context_permission(payload: dict, required: str) -> bool:
    if required in set(payload.get("permissions") or []):
        return True
    wildcard_permissions = payload.get("wildcard_permissions") or {}
    return any(required in set(wildcard_permissions.get(wildcard) or []) for wildcard in payload.get("wildcards") or [])
