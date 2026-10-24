from __future__ import annotations

from typing import Any

from cities_light.models import City, Country, Region, SubRegion
from mainapps.accounts.models import User
from mainapps.profile.models import CompanyMembership, CompanyProfile
from subapps.kafka.client import publish_event
from subapps.kafka.producers.platform_events import publish_audit_fact
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


def _geography_name(model, value: Any) -> str:
    """Publish readable location values rather than cities-light primary keys."""
    if value in (None, ""):
        return ""
    try:
        return model.objects.only("name").get(id=int(value)).name
    except (TypeError, ValueError, model.DoesNotExist):
        return str(value).strip()


def _serialize_headquarters_address(profile: CompanyProfile) -> dict[str, Any]:
    address = getattr(profile, "headquarters_address", None)
    if address is None:
        return {}
    return {
        "street_number": address.street_number,
        "street": str(address.street or "").strip(),
        "apt_number": address.apt_number,
        "city": _geography_name(City, address.city),
        "subregion": _geography_name(SubRegion, address.subregion),
        "region": _geography_name(Region, address.region),
        "country": _geography_name(Country, address.country),
        "postal_code": str(address.postal_code or "").strip(),
    }


def _serialize_company_profile(profile: CompanyProfile) -> dict[str, Any]:
    display_name = profile.name or profile.company_code or str(profile.id)
    headquarters_address = getattr(profile, "headquarters_address", None)
    return {
        "profile_id": profile.id,
        "company_code": profile.company_code,
        "display_name": display_name,
        "logo_url": profile.logo.url if getattr(profile, "logo", None) else "",
        # Keep the legacy snapshot during the compatibility window. Consumers should
        # use the opaque shared ID for address resolution going forward.
        "headquarters_address_id": str(headquarters_address.shared_address_id) if headquarters_address and headquarters_address.shared_address_id else None,
        "headquarters_address": _serialize_headquarters_address(profile),
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
    payload = _serialize_user(user)
    event = publish_event(
        IDENTITY_USER_TOPIC,
        "identity.user.upserted",
        payload,
        key=str(user.id),
    )
    publish_audit_fact(
        event_name="identity.user.upserted",
        payload=payload,
        actor={"user_id": str(user.id), "email": user.email, "name": payload["full_name"]},
        target={"type": "user", "id": str(user.id), "label": payload["full_name"]},
        summary=f"User profile synced for {user.email}.",
        visibility_scope="platform",
        key=str(user.id),
    )
    return event


def publish_user_deleted(user: User) -> dict[str, Any]:
    payload = _serialize_user(user)
    payload["is_active"] = False
    event = publish_event(
        IDENTITY_USER_TOPIC,
        "identity.user.deleted",
        payload,
        key=str(user.id),
    )
    publish_audit_fact(
        event_name="identity.user.deleted",
        payload=payload,
        actor={"user_id": str(user.id), "email": user.email, "name": payload["full_name"]},
        target={"type": "user", "id": str(user.id), "label": payload["full_name"]},
        summary=f"User profile deactivated for {user.email}.",
        severity="warning",
        visibility_scope="platform",
        key=str(user.id),
    )
    return event


def publish_company_profile_upserted(profile: CompanyProfile) -> dict[str, Any]:
    payload = _serialize_company_profile(profile)
    event = publish_event(
        IDENTITY_COMPANY_PROFILE_TOPIC,
        "identity.company_profile.upserted",
        payload,
        key=str(profile.id),
    )
    publish_audit_fact(
        event_name="identity.company_profile.upserted",
        payload=payload,
        workspace_id=str(profile.id),
        actor={"user_id": str(profile.owner_id or ""), "role": "owner"},
        target={"type": "company_profile", "id": str(profile.id), "label": payload["display_name"]},
        summary=f"Workspace profile updated for {payload['display_name']}.",
        key=str(profile.id),
    )
    return event


def publish_company_profile_deleted(profile: CompanyProfile) -> dict[str, Any]:
    payload = _serialize_company_profile(profile)
    payload["is_active"] = False
    event = publish_event(
        IDENTITY_COMPANY_PROFILE_TOPIC,
        "identity.company_profile.deleted",
        payload,
        key=str(profile.id),
    )
    publish_audit_fact(
        event_name="identity.company_profile.deleted",
        payload=payload,
        workspace_id=str(profile.id),
        actor={"user_id": str(profile.owner_id or ""), "role": "owner"},
        target={"type": "company_profile", "id": str(profile.id), "label": payload["display_name"]},
        summary=f"Workspace profile archived for {payload['display_name']}.",
        severity="warning",
        key=str(profile.id),
    )
    return event


def publish_company_membership_upserted(membership: CompanyMembership) -> dict[str, Any]:
    payload = _serialize_membership(membership)
    event = publish_event(
        IDENTITY_MEMBERSHIP_TOPIC,
        "identity.membership.upserted",
        payload,
        key=f"{membership.profile_id}:{membership.user_id}",
    )
    publish_audit_fact(
        event_name="identity.membership.upserted",
        payload=payload,
        workspace_id=str(membership.profile_id),
        actor={"user_id": str(membership.user_id), "email": payload["user"]["email"], "role": payload["role"]},
        target={
            "type": "membership",
            "id": f"{membership.profile_id}:{membership.user_id}",
            "label": payload["profile"]["display_name"],
            "reference_number": payload["profile"]["company_code"],
        },
        summary=f"{payload['user']['full_name']} membership synced for {payload['profile']['display_name']}.",
        key=f"{membership.profile_id}:{membership.user_id}",
    )
    return event


def publish_company_membership_deleted(membership: CompanyMembership) -> dict[str, Any]:
    payload = _serialize_membership(membership)
    payload["is_active"] = False
    event = publish_event(
        IDENTITY_MEMBERSHIP_TOPIC,
        "identity.membership.deleted",
        payload,
        key=f"{membership.profile_id}:{membership.user_id}",
    )
    publish_audit_fact(
        event_name="identity.membership.deleted",
        payload=payload,
        workspace_id=str(membership.profile_id),
        actor={"user_id": str(membership.user_id), "email": payload["user"]["email"], "role": payload["role"]},
        target={
            "type": "membership",
            "id": f"{membership.profile_id}:{membership.user_id}",
            "label": payload["profile"]["display_name"],
            "reference_number": payload["profile"]["company_code"],
        },
        summary=f"{payload['user']['full_name']} membership removed from {payload['profile']['display_name']}.",
        severity="warning",
        key=f"{membership.profile_id}:{membership.user_id}",
    )
    return event
