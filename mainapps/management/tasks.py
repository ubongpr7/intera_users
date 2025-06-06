from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from mainapps.management.models import ActivityLog
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def async_log_activity(log_data: dict):
    """
    Celery task for asynchronous activity logging
    """
    try:
        user_id = log_data.pop('user_id', None)
        user = None
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User with ID {user_id} not found for activity logging")

        ActivityLog.objects.create(
            user=user,
            **log_data
        )
        
    except KeyError as e:
        logger.error(f"Missing required field in activity log: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create async activity log: {str(e)}", exc_info=True)