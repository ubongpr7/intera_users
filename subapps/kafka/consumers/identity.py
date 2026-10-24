from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _log_event(envelope: dict[str, Any], **context: Any) -> bool:
    logger.info(
        "Consumed Kafka event topic=%s event=%s source=%s key=%s",
        context.get("topic"),
        envelope.get("event_name"),
        envelope.get("source_service"),
        context.get("message_key"),
    )
    return True


def handle_identity_user_event(envelope: dict[str, Any], **context: Any) -> bool:
    return _log_event(envelope, **context)


def handle_identity_company_profile_event(envelope: dict[str, Any], **context: Any) -> bool:
    return _log_event(envelope, **context)


def handle_identity_membership_event(envelope: dict[str, Any], **context: Any) -> bool:
    return _log_event(envelope, **context)
