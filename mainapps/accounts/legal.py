from __future__ import annotations

from typing import Any

from django.db import IntegrityError
from django.utils import timezone

TERMS_POLICY_VERSION = "2026-08-02"
PRIVACY_POLICY_VERSION = "2026-08-02"


def _client_ip(request: Any) -> str | None:
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record_signup_consents(user, *, request=None, source: str = "signup") -> None:
    """Store the policy versions accepted as part of account creation."""
    from .models import LegalConsent

    accepted_at = timezone.now()
    defaults = {
        "accepted_at": accepted_at,
        "ip_address": _client_ip(request),
        "user_agent": (request.META.get("HTTP_USER_AGENT", "") if request else "")[:1024],
        "source": source[:32],
    }
    for consent_type, version in (
        (LegalConsent.ConsentType.TERMS, TERMS_POLICY_VERSION),
        (LegalConsent.ConsentType.PRIVACY, PRIVACY_POLICY_VERSION),
    ):
        try:
            LegalConsent.objects.get_or_create(
                user=user,
                consent_type=consent_type,
                policy_version=version,
                defaults=defaults,
            )
        except IntegrityError:
            # Another request may have recorded the same acceptance concurrently.
            pass


def validate_signup_consents(attrs: dict) -> dict:
    """Reject account creation unless both current policies were accepted."""
    from rest_framework import serializers

    if attrs.pop("terms_accepted", False) is not True:
        raise serializers.ValidationError(
            {"terms_accepted": "You must read and agree to the Terms and Conditions."}
        )
    if attrs.pop("privacy_accepted", False) is not True:
        raise serializers.ValidationError(
            {"privacy_accepted": "You must read and agree to the Privacy Policy."}
        )
    return attrs
