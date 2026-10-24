def get_company_or_profile(user, profile_id=None, support_access_grant_id=None):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    from mainapps.profile.models import CompanyProfile
    from mainapps.profile.support_access import get_active_support_grant

    if profile_id:
        profile = CompanyProfile.objects.filter(id=profile_id).first()
        if not profile:
            return None
        if profile.owner_id == user.id:
            return profile
        membership = user.company_memberships.filter(profile=profile, is_active=True).first()
        if membership:
            return profile
        support_grant = get_active_support_grant(
            user,
            profile=profile,
            grant_id=support_access_grant_id,
        )
        return profile if support_grant else None

    if user.profile_id:
        profile = CompanyProfile.objects.filter(id=user.profile_id).first()
        if profile and (
            profile.owner_id == user.id
            or user.company_memberships.filter(profile=profile, is_active=True).exists()
        ):
            return profile
        if profile:
            support_grant = get_active_support_grant(
                user,
                profile=profile,
                grant_id=support_access_grant_id,
            )
            if support_grant:
                return profile

    owned_company = user.owned_companies.order_by("-created_at").first()
    if owned_company:
        return owned_company

    membership = user.company_memberships.filter(is_active=True).select_related("profile").first()
    if membership:
        return membership.profile

    support_grant = get_active_support_grant(
        user,
        grant_id=support_access_grant_id,
    )
    return support_grant.profile if support_grant else None
