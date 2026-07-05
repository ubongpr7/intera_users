import json
import logging
import os
from urllib import error, request
from rest_framework.exceptions import PermissionDenied
logger = logging.getLogger(__name__)

def enforce_subscription_limit(*, profile_id, feature, usage, requested=1):
    mode = os.getenv('SUBSCRIPTION_ENFORCEMENT_MODE', 'off').lower()
    if mode == 'off': return None
    req = request.Request(
        f"{os.getenv('SUBSCRIPTION_SERVICE_URL', 'http://subscriptions:8550').rstrip('/')}/internal/v1/entitlements/",
        data=json.dumps({'profile_id': str(profile_id), 'feature': feature, 'usage': usage, 'requested': requested}).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'X-Intera-Service-Key': os.getenv('SUBSCRIPTION_SERVICE_KEY', '')},
    )
    try:
        with request.urlopen(req, timeout=float(os.getenv('SUBSCRIPTION_SERVICE_TIMEOUT', '2.0'))) as response:
            decision = json.loads(response.read().decode())
    except (error.URLError, TimeoutError, ValueError) as exc:
        logger.warning('Subscription check unavailable feature=%s profile=%s: %s', feature, profile_id, exc)
        if mode == 'enforce': raise PermissionDenied({'code': 'subscription_service_unavailable', 'detail': 'Subscription limits could not be verified. Please retry.'})
        return None
    if not decision.get('allowed') and mode == 'enforce':
        raise PermissionDenied({'code': 'subscription_limit_reached', 'detail': 'Your current plan limit has been reached.', 'feature': feature, 'limit': decision.get('limit'), 'usage': usage, 'upgrade_required': True})
    return decision
