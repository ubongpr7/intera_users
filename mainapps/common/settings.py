def get_company_or_profile(user, profile_id=None):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    from mainapps.profile.models import CompanyProfile

    if profile_id:
        profile = CompanyProfile.objects.filter(id=profile_id).first()
        if not profile:
            return None
        if profile.owner_id == user.id:
            return profile
        membership = user.company_memberships.filter(profile=profile, is_active=True).first()
        return profile if membership else None

    if user.profile_id:
        profile = CompanyProfile.objects.filter(id=user.profile_id).first()
        if profile and (
            profile.owner_id == user.id
            or user.company_memberships.filter(profile=profile, is_active=True).exists()
        ):
            return profile

    owned_company = user.owned_companies.order_by("-created_at").first()
    if owned_company:
        return owned_company

    membership = user.company_memberships.filter(is_active=True).select_related("profile").first()
    return membership.profile if membership else None

