from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from subapps.kafka.producers import publish_support_access_grant_expired

from .models import CompanyMembership, CompanyProfile, SupportAccessGrant


@dataclass(frozen=True)
class ResolvedProfileAccess:
    profile: CompanyProfile | None
    support_grant: SupportAccessGrant | None = None

    @property
    def is_support(self) -> bool:
        return self.support_grant is not None


def user_has_direct_profile_access(user, profile: CompanyProfile | None) -> bool:
    if not profile:
        return False
    if profile.owner_id == user.id:
        return True
    return CompanyMembership.objects.filter(
        user=user,
        profile=profile,
        is_active=True,
    ).exists()


def get_active_support_grant(
    user,
    *,
    profile: CompanyProfile | None = None,
    profile_id=None,
    grant_id=None,
    at_time=None,
) -> SupportAccessGrant | None:
    current_time = at_time or timezone.now()
    grants = SupportAccessGrant.objects.select_related("profile", "grantee_user").filter(
        grantee_user=user,
        revoked_at__isnull=True,
        starts_at__lte=current_time,
        expires_at__gt=current_time,
    ).exclude(status__in=[SupportAccessGrant.Status.CONSUMED, SupportAccessGrant.Status.DECLINED])

    if grant_id:
        grants = grants.filter(id=grant_id)
    if profile is not None:
        grants = grants.filter(profile=profile)
    elif profile_id is not None:
        grants = grants.filter(profile_id=profile_id)

    grant = grants.order_by("starts_at", "created_at").first()
    if not grant:
        return None

    if grant.refresh_status(save=True) != SupportAccessGrant.Status.ACTIVE:
        return None
    return grant


def list_support_access_grants(user, *, at_time=None) -> list[SupportAccessGrant]:
    current_time = at_time or timezone.now()
    grants = (
        SupportAccessGrant.objects.select_related("profile")
        .filter(
            grantee_user=user,
            revoked_at__isnull=True,
            starts_at__lte=current_time,
            expires_at__gt=current_time,
        )
        .exclude(status__in=[SupportAccessGrant.Status.CONSUMED, SupportAccessGrant.Status.DECLINED])
        .order_by("profile__name", "starts_at")
    )

    active_grants: list[SupportAccessGrant] = []
    for grant in grants:
        if grant.refresh_status(save=True) == SupportAccessGrant.Status.ACTIVE:
            active_grants.append(grant)
    return active_grants


def list_accessible_profile_contexts(user) -> list[ResolvedProfileAccess]:
    contexts_by_profile_id: dict[str, ResolvedProfileAccess] = {}

    for profile in CompanyProfile.objects.filter(owner=user).order_by("name"):
        contexts_by_profile_id[str(profile.id)] = ResolvedProfileAccess(profile=profile)

    memberships = (
        CompanyMembership.objects.filter(user=user, is_active=True)
        .select_related("profile")
        .order_by("profile__name")
    )
    for membership in memberships:
        contexts_by_profile_id[str(membership.profile_id)] = ResolvedProfileAccess(profile=membership.profile)

    for grant in list_support_access_grants(user):
        contexts_by_profile_id.setdefault(
            str(grant.profile_id),
            ResolvedProfileAccess(profile=grant.profile, support_grant=grant),
        )

    return list(contexts_by_profile_id.values())


def resolve_profile_access(
    user,
    *,
    profile_id=None,
    company_code=None,
    support_access_grant_id=None,
) -> ResolvedProfileAccess:
    requested_profile = None
    if profile_id:
        requested_profile = CompanyProfile.objects.filter(id=profile_id).first()
    elif company_code:
        requested_profile = CompanyProfile.objects.filter(company_code__iexact=company_code).first()

    if support_access_grant_id:
        support_grant = get_active_support_grant(
            user,
            profile=requested_profile,
            grant_id=support_access_grant_id,
        )
        if support_grant:
            requested_profile = support_grant.profile

    if requested_profile:
        if user_has_direct_profile_access(user, requested_profile):
            return ResolvedProfileAccess(profile=requested_profile)

        support_grant = get_active_support_grant(
            user,
            profile=requested_profile,
            grant_id=support_access_grant_id,
        )
        if support_grant:
            return ResolvedProfileAccess(profile=requested_profile, support_grant=support_grant)
        return ResolvedProfileAccess(profile=None)

    if user.profile_id:
        current_profile = CompanyProfile.objects.filter(id=user.profile_id).first()
        if current_profile:
            if user_has_direct_profile_access(user, current_profile):
                return ResolvedProfileAccess(profile=current_profile)
            support_grant = get_active_support_grant(
                user,
                profile=current_profile,
                grant_id=support_access_grant_id,
            )
            if support_grant:
                return ResolvedProfileAccess(profile=current_profile, support_grant=support_grant)

    if support_access_grant_id:
        support_grant = get_active_support_grant(user, grant_id=support_access_grant_id)
        if support_grant:
            return ResolvedProfileAccess(profile=support_grant.profile, support_grant=support_grant)

    contexts = list_accessible_profile_contexts(user)
    if len(contexts) == 1:
        return contexts[0]

    direct_contexts = [context for context in contexts if not context.is_support]
    if len(direct_contexts) == 1 and len(contexts) == 1:
        return direct_contexts[0]

    return ResolvedProfileAccess(profile=None)


def validate_support_token(user, *, profile_id=None, support_access_grant_id=None) -> bool:
    if not support_access_grant_id:
        return True

    support_grant = get_active_support_grant(
        user,
        profile_id=profile_id,
        grant_id=support_access_grant_id,
    )
    return support_grant is not None


def expire_support_grants(*, user=None, profile=None) -> int:
    filters = Q(
        revoked_at__isnull=True,
        expires_at__lte=timezone.now(),
    ) & Q(status__in=[SupportAccessGrant.Status.PENDING, SupportAccessGrant.Status.ACTIVE])
    if user is not None:
        filters &= Q(grantee_user=user)
    if profile is not None:
        filters &= Q(profile=profile)

    grants = list(
        SupportAccessGrant.objects.select_related(
            "profile",
            "grantee_user",
            "created_by",
            "approved_by",
            "revoked_by",
        )
        .prefetch_related("custom_permissions")
        .filter(filters)
        .exclude(status=SupportAccessGrant.Status.EXPIRED)
    )
    for grant in grants:
        grant.status = SupportAccessGrant.Status.EXPIRED
        grant.save(update_fields=["status", "updated_at"])
        publish_support_access_grant_expired(grant)
    return len(grants)
