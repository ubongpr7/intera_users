from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import User, VerificationCode
from subapps.kafka.producers.identity import publish_user_deleted, publish_user_upserted


@receiver(post_save, sender=User)
def post_save_initialize_user(sender, instance, created, **kwargs):
    if not created:
        transaction.on_commit(lambda: publish_user_upserted(instance))
        return

    VerificationCode.objects.get_or_create(user=instance)
    transaction.on_commit(lambda: publish_user_upserted(instance))


@receiver(post_delete, sender=User)
def post_delete_publish_user(sender, instance, **kwargs):
    del sender, kwargs
    transaction.on_commit(lambda: publish_user_deleted(instance))
