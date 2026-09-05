from __future__ import annotations

import os

PROJECT_TOPIC_PREFIXES = (
    "identity.",
    "catalog.",
    "inventory.",
    "pos.",
    "workspace.",
    "notification.",
    "audit_events",
    "notification_events",
    "support_access_events",
    "affiliate_program",
)


def namespaced_topic(topic: str) -> str:
    namespace = os.getenv("KAFKA_TOPIC_NAMESPACE", "").strip().strip(".")
    topic = topic.strip()
    if not namespace or not topic:
        return topic
    if topic.startswith(f"{namespace}.") and topic.removeprefix(f"{namespace}.").startswith(PROJECT_TOPIC_PREFIXES):
        return topic
    return f"{namespace}.{topic}"


IDENTITY_USER_TOPIC = namespaced_topic("identity.user")
IDENTITY_COMPANY_PROFILE_TOPIC = namespaced_topic("identity.company_profile")
IDENTITY_MEMBERSHIP_TOPIC = namespaced_topic("identity.membership")
IDENTITY_PERMISSION_CONTEXT_TOPIC = namespaced_topic("identity.permission_context")
WORKSPACE_SUBSCRIPTION_TOPIC = namespaced_topic("workspace.subscription")

CATALOG_PRODUCT_TOPIC = namespaced_topic("catalog.product")
CATALOG_VARIANT_TOPIC = namespaced_topic("catalog.variant")
INVENTORY_AVAILABILITY_TOPIC = namespaced_topic("inventory.availability")
POS_ORDER_TOPIC = namespaced_topic("pos.order")
AUDIT_EVENTS_TOPIC = namespaced_topic("audit_events")
NOTIFICATION_EVENTS_TOPIC = namespaced_topic("notification_events")
SUPPORT_ACCESS_EVENTS_TOPIC = namespaced_topic("support_access_events")
AFFILIATE_PROGRAM_TOPIC = namespaced_topic("affiliate_program")
