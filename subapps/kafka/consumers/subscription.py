from __future__ import annotations

import logging
from typing import Any

from mainapps.profile.models import CompanyProfile

logger = logging.getLogger(__name__)


def _profile_id_from_envelope(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload") or {}
    candidate = (
        payload.get("profile_id")
        or payload.get("workspace_id")
        or envelope.get("profile_id")
        or envelope.get("workspace_id")
    )
    return str(candidate or "").strip()


def handle_subscription_workspace_event(envelope: dict[str, Any], **context: Any) -> bool:
    profile_id = _profile_id_from_envelope(envelope)
    if not profile_id:
        logger.warning(
            "Skipping subscription workspace event without profile_id topic=%s event=%s",
            context.get("topic"),
            envelope.get("event_name"),
        )
        return False

    profile = CompanyProfile.objects.filter(id=profile_id).first()
    if profile is None:
        logger.warning(
            "Skipping subscription workspace event for missing profile_id=%s topic=%s event=%s",
            profile_id,
            context.get("topic"),
            envelope.get("event_name"),
        )
        return False

    snapshot = envelope.get("payload") or {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    profile.subscription_snapshot = snapshot
    profile.save(update_fields=["subscription_snapshot", "updated_at"])
    logger.info(
        "Workspace subscription snapshot synced profile_id=%s event=%s",
        profile_id,
        envelope.get("event_name"),
    )
    return True
