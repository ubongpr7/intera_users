from subapps.kafka.consumers.identity import (
    handle_identity_company_profile_event,
    handle_identity_membership_event,
    handle_identity_user_event,
)
from subapps.kafka.topics import (
    IDENTITY_COMPANY_PROFILE_TOPIC,
    IDENTITY_MEMBERSHIP_TOPIC,
    IDENTITY_USER_TOPIC,
)

EVENT_HANDLERS = {
    IDENTITY_USER_TOPIC: handle_identity_user_event,
    IDENTITY_COMPANY_PROFILE_TOPIC: handle_identity_company_profile_event,
    IDENTITY_MEMBERSHIP_TOPIC: handle_identity_membership_event,
}
