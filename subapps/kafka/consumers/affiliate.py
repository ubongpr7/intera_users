from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging

from django.db import transaction

from mainapps.accounts.models import ReferralPayout, User

logger = logging.getLogger(__name__)


def _decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def handle_affiliate_commission_event(event, **context):
    del context
    payload = event.get('payload') if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        logger.warning('Ignoring affiliate event with invalid payload.')
        return True

    payment_reference = str(payload.get('payment_reference') or '').strip()
    referred_user_id = str(payload.get('referred_user_id') or payload.get('owner_user_id') or '').strip()
    if not payment_reference or not referred_user_id:
        logger.warning('Ignoring affiliate event without payment reference or referred user.')
        return True

    referred_user = User.objects.filter(pk=referred_user_id).first()
    if referred_user is None:
        logger.warning('Deferring affiliate event; referred user %s does not exist yet.', referred_user_id)
        return False

    referrer_id = str(payload.get('referrer_user_id') or referred_user.referred_by_id or '').strip()
    if not referrer_id:
        return True
    referrer = User.objects.filter(pk=referrer_id).first()
    if referrer is None:
        logger.warning('Deferring affiliate event; referrer %s does not exist yet.', referrer_id)
        return False

    payment_amount = _decimal(payload.get('payment_amount'))
    commission_rate = _decimal(payload.get('commission_rate'), '0.05')
    commission_amount = _decimal(payload.get('commission_amount'))
    if commission_amount <= 0 and payment_amount > 0:
        commission_amount = (payment_amount * commission_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    with transaction.atomic():
        ReferralPayout.objects.get_or_create(
            payment_reference=payment_reference,
            defaults={
                'referrer_user': referrer,
                'referred_user': referred_user,
                'commission_rate': commission_rate,
                'payment_amount': payment_amount,
                'payout_amount': commission_amount,
                'currency': str(payload.get('currency') or 'USD')[:3].upper(),
                'payment_id': str(payload.get('payment_id') or ''),
                'profile_id': str(payload.get('profile_id') or payload.get('workspace_id') or ''),
                'plan_slug': str(payload.get('plan_slug') or ''),
                'metadata': payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
            },
        )
    return True
