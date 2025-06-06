# core/models/mixins.py
from django.db import models
from .activity_logger import log_user_activity

class ActivityLogMixin(models.Model):
    class Meta:
        abstract = True

    def log_action(self, action: str, user=None, details: dict = None):
        log_user_activity(
            user=user,
            action=action,
            model_name=self._meta.model_name,
            object_id=self.pk,
            details=details
        )

    def save(self, *args, **kwargs):
        action = 'UPDATE' if self.pk else 'CREATE'
        super().save(*args, **kwargs)
        self.log_action(action)

    def delete(self, *args, **kwargs):
        self.log_action('DELETE')
        super().delete(*args, **kwargs)