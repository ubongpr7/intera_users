import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import User, VerificationCode
from subapps.kafka.producers.identity import publish_user_deleted, publish_user_upserted

logger = logging.getLogger(__name__)


def _publish_after_commit(callback, event_name):
    """Do not turn a committed database mutation into a misleading 500."""
    def publish() -> None:
        try:
            callback()
        except Exception:
            logger.exception("Failed to publish %s event after database commit", event_name)

    transaction.on_commit(publish)


@receiver(post_save, sender=User)
def post_save_initialize_user(sender, instance, created, **kwargs):
    if not created:
        _publish_after_commit(lambda: publish_user_upserted(instance), "identity.user.upserted")
        return

    VerificationCode.objects.get_or_create(user=instance)
    _publish_after_commit(lambda: publish_user_upserted(instance), "identity.user.upserted")


@receiver(post_delete, sender=User)
def post_delete_publish_user(sender, instance, **kwargs):
    del sender, kwargs
    _publish_after_commit(lambda: publish_user_deleted(instance), "identity.user.deleted")
