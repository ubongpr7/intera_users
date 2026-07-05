from django.core.management import call_command
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import CompanyMembership, CompanyProfile
from subapps.kafka.producers.access_control import publish_membership_permissions_updated
from subapps.kafka.producers.identity import (
    publish_company_membership_deleted,
    publish_company_membership_upserted,
    publish_company_profile_deleted,
    publish_company_profile_upserted,
)


@receiver(post_save, sender=CompanyProfile)
def create_default_roles_and_groups(sender, instance, created, **kwargs):
    if not created:
        transaction.on_commit(lambda: publish_company_profile_upserted(instance))
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

    def bootstrap_profile_defaults():
        call_command("setup_default_roles", "--profile-id", str(instance.id))
        call_command("setup_default_groups", "--profile-id", str(instance.id))

    transaction.on_commit(bootstrap_profile_defaults)
    transaction.on_commit(lambda: publish_company_profile_upserted(instance))


@receiver(post_delete, sender=CompanyProfile)
def publish_deleted_company_profile(sender, instance, **kwargs):
    del sender, kwargs
    transaction.on_commit(lambda: publish_company_profile_deleted(instance))


@receiver(post_save, sender=CompanyMembership)
def publish_company_membership(sender, instance, **kwargs):
    del sender, kwargs
    transaction.on_commit(lambda: publish_company_membership_upserted(instance))


@receiver(post_delete, sender=CompanyMembership)
def publish_deleted_company_membership(sender, instance, **kwargs):
    del sender, kwargs
    transaction.on_commit(lambda: publish_company_membership_deleted(instance))


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
        transaction.on_commit(
            lambda: publish_membership_permissions_updated(
                actor={
                    "type": "system",
                    "name": "company_membership_permissions_signal",
                },
                membership=instance,
                before_permissions=before_permissions,
                after_permissions=after_permissions,
            )
        )

    transaction.on_commit(lambda: publish_company_membership_upserted(instance))
