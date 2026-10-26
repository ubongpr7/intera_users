from decimal import Decimal

from .models import AffiliatePartner, User


def affiliate_partner_for_user(user):
    """Resolve the partner account before falling back to the user's email."""
    partner = getattr(user, "affiliate_partner_account", None)
    if partner is not None:
        return partner
    return AffiliatePartner.objects.filter(email__iexact=user.email).first()


def sync_affiliate_account_user(partner, user=None):
    """Keep the reserved user identity aligned with the partner record."""
    user = user or partner.account_user
    if user is None:
        return None
    updates = {
        "is_affiliate_marketer": True,
        "referral_code": partner.code,
        "referral_commission_rate": partner.commission_rate,
    }
    if user.referred_by_affiliate_partner_id == partner.pk:
        updates["referred_by_affiliate_partner"] = None
    User.objects.filter(pk=user.pk).update(
        **updates,
    )
    user.is_affiliate_marketer = True
    user.referral_code = partner.code
    user.referral_commission_rate = partner.commission_rate
    if user.referred_by_affiliate_partner_id == partner.pk:
        user.referred_by_affiliate_partner = None
        user.referred_by_affiliate_partner_id = None
    return user


def commission_rate_percent(rate):
    """Render stored fractional rates (0.20) as human percentages (20%)."""
    value = (Decimal(str(rate)) * Decimal("100")).normalize()
    return format(value, "f") + "%"
