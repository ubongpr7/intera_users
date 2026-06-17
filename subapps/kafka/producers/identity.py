from __future__ import annotations

from typing import Any

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyMembership, CompanyProfile
from subapps.kafka.client import publish_event
from subapps.kafka.topics import (
    IDENTITY_COMPANY_PROFILE_TOPIC,
    IDENTITY_MEMBERSHIP_TOPIC,
    IDENTITY_USER_TOPIC,
)


def _serialize_user(user: User) -> dict[str, Any]:
    full_name = (getattr(user, "get_full_name", "") or "").strip()
    if not full_name:
        full_name = f"{user.first_name} {user.last_name}".strip()
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": full_name or user.email,
        "is_active": user.is_active,
    }


def _serialize_company_profile(profile: CompanyProfile) -> dict[str, Any]:
    display_name = profile.name or profile.company_code or str(profile.id)
    return {
        "profile_id": profile.id,
        "company_code": profile.company_code,
        "display_name": display_name,
        "industry": profile.industry,
        "owner_user_id": profile.owner_id,
        "is_active": True,
    }


def _serialize_membership(membership: CompanyMembership) -> dict[str, Any]:
    permissions = list(membership.custom_permissions.values_list("codename", flat=True))
    return {
        "profile_id": membership.profile_id,
        "user_id": membership.user_id,
        "role": membership.role,
        "permissions": permissions,
        "is_active": membership.is_active,
        "profile": _serialize_company_profile(membership.profile),
        "user": _serialize_user(membership.user),
    }


def publish_user_upserted(user: User) -> dict[str, Any]:
    return publish_event(
        IDENTITY_USER_TOPIC,
        "identity.user.upserted",
        _serialize_user(user),
        key=str(user.id),
    )


def publish_user_deleted(user: User) -> dict[str, Any]:
    payload = _serialize_user(user)
    payload["is_active"] = False
    return publish_event(
        IDENTITY_USER_TOPIC,
        "identity.user.deleted",
        payload,
        key=str(user.id),
    )


def publish_company_profile_upserted(profile: CompanyProfile) -> dict[str, Any]:
    return publish_event(
        IDENTITY_COMPANY_PROFILE_TOPIC,
        "identity.company_profile.upserted",
        _serialize_company_profile(profile),
        key=str(profile.id),
    )


def publish_company_profile_deleted(profile: CompanyProfile) -> dict[str, Any]:
    payload = _serialize_company_profile(profile)
    payload["is_active"] = False
    return publish_event(
        IDENTITY_COMPANY_PROFILE_TOPIC,
        "identity.company_profile.deleted",
        payload,
        key=str(profile.id),
    )


def publish_company_membership_upserted(membership: CompanyMembership) -> dict[str, Any]:
    return publish_event(
        IDENTITY_MEMBERSHIP_TOPIC,
        "identity.membership.upserted",
        _serialize_membership(membership),
        key=f"{membership.profile_id}:{membership.user_id}",
    )


def publish_company_membership_deleted(membership: CompanyMembership) -> dict[str, Any]:
    payload = _serialize_membership(membership)
    payload["is_active"] = False
    return publish_event(
        IDENTITY_MEMBERSHIP_TOPIC,
        "identity.membership.deleted",
        payload,
        key=f"{membership.profile_id}:{membership.user_id}",
    )
