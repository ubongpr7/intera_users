import logging

from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import CompanyMembership, CompanyProfile, CompanyProfileAddress
from subapps.kafka.producers.access_control import publish_membership_permissions_updated
from subapps.kafka.producers.identity import (
    publish_company_membership_deleted,
    publish_company_membership_upserted,
    publish_company_profile_deleted,
    publish_company_profile_upserted,
)

logger = logging.getLogger(__name__)


def _publish_after_commit(callback, event_name):
    """Keep committed profile changes successful when event delivery is unavailable."""
    def publish() -> None:
        try:
            callback()
        except Exception:
            logger.exception("Failed to publish %s event after database commit", event_name)

    transaction.on_commit(publish)


@receiver(post_save, sender=CompanyProfile)
def create_default_roles_and_groups(sender, instance, created, **kwargs):
    if not created:
        _publish_after_commit(lambda: publish_company_profile_upserted(instance), "identity.company_profile.upserted")
        return

    if instance.owner_id:
        CompanyMembership.objects.update_or_create(
            user_id=instance.owner_id,
            profile=instance,
            defaults={
                "role": CompanyMembership.MembershipRole.OWNER,
                "is_active": True,
            },
        )

    _publish_after_commit(lambda: publish_company_profile_upserted(instance), "identity.company_profile.upserted")


@receiver(post_delete, sender=CompanyProfile)
def publish_deleted_company_profile(sender, instance, **kwargs):
    del sender, kwargs
    _publish_after_commit(lambda: publish_company_profile_deleted(instance), "identity.company_profile.deleted")


def _publish_address_profile(profile_id: int | None) -> None:
    if not profile_id:
        return

    def publish() -> None:
        profile = CompanyProfile.objects.select_related("headquarters_address").filter(pk=profile_id).first()
        if profile is not None:
            publish_company_profile_upserted(profile)

    _publish_after_commit(publish, "identity.company_profile.upserted")


@receiver(post_save, sender=CompanyProfileAddress)
def publish_company_profile_after_address_save(sender, instance, **kwargs):
    del sender, kwargs
    _publish_address_profile(instance.profile_id)


@receiver(post_delete, sender=CompanyProfileAddress)
def publish_company_profile_after_address_delete(sender, instance, **kwargs):
    del sender, kwargs
    _publish_address_profile(instance.profile_id)


@receiver(post_save, sender=CompanyMembership)
def publish_company_membership(sender, instance, **kwargs):
    del sender, kwargs
    _publish_after_commit(lambda: publish_company_membership_upserted(instance), "identity.membership.upserted")


@receiver(post_delete, sender=CompanyMembership)
def publish_deleted_company_membership(sender, instance, **kwargs):
    del sender, kwargs
    _publish_after_commit(lambda: publish_company_membership_deleted(instance), "identity.membership.deleted")


@receiver(m2m_changed, sender=CompanyMembership.custom_permissions.through)
def publish_company_membership_permissions(sender, instance, action, **kwargs):
    del sender, kwargs
    if action in {"pre_add", "pre_remove", "pre_clear"}:
        instance._audit_membership_permissions_before = sorted(
            str(codename).strip()
            for codename in instance.custom_permissions.values_list("codename", flat=True)
            if str(codename).strip()
        )
        return

    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    before_permissions = list(getattr(instance, "_audit_membership_permissions_before", []))
    after_permissions = sorted(
        str(codename).strip()
        for codename in instance.custom_permissions.values_list("codename", flat=True)
        if str(codename).strip()
    )
    if hasattr(instance, "_audit_membership_permissions_before"):
        delattr(instance, "_audit_membership_permissions_before")

    if before_permissions != after_permissions:
        _publish_after_commit(
            lambda: publish_membership_permissions_updated(
                actor={
                    "type": "system",
                    "name": "company_membership_permissions_signal",
                },
                membership=instance,
                before_permissions=before_permissions,
                after_permissions=after_permissions,
            ),
            "identity.membership.permissions_updated",
        )

    _publish_after_commit(lambda: publish_company_membership_upserted(instance), "identity.membership.upserted")
