from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from ..models import ActivityLog
from django.db import models
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
User = get_user_model()

def log_user_activity(
    user = None,
    action: Optional[str] = None,
    model_name: Optional[str] = None,
    object_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    instance: Optional[models.Model] = None,
    async_log: bool = False
) -> None:
    """
    Robust user activity logger with enhanced validation and async support
    """
    try:
        # Resolve user from instance if available
        if not user and hasattr(instance, 'request'):
            try:
                user = instance.request.user
            except AttributeError:
                pass

        # Validate required parameters
        validation_errors = []
        
        # Auto-populate model information from instance
        if instance:
            if not model_name:
                model_name = instance._meta.model_name
            if not object_id and instance.pk:
                object_id = instance.pk
            elif not object_id:
                validation_errors.append("Instance missing primary key")

        # Parameter validation
        if not action:
            validation_errors.append("Missing action parameter")
        if not model_name:
            validation_errors.append("Missing model_name parameter")
        if not object_id:
            validation_errors.append("Missing object_id parameter")

        if validation_errors:
            raise ValueError(", ".join(validation_errors))

        # Prepare base log data
        log_data = {
            'action': action,
            'model_name': model_name,
            'object_id': object_id,
            'details': details or {}
        }

        if async_log:
            # Prepare for async task (user must be ID reference)
            async_data = log_data.copy()
            async_data['user_id'] = user.id if user else None
            _dispatch_async_log(async_data)
        else:
            # Synchronous logging with user instance
            ActivityLog.objects.create(
                user=user,
                **log_data
            )

    except ObjectDoesNotExist as e:
        logger.error(f"Reference error in activity log: {str(e)}", exc_info=True)
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Critical logging failure: {str(e)}", exc_info=True)

def _dispatch_async_log(data: Dict[str, Any]) -> None:
    """Handle async logging with proper serialization"""
    try:
        from ..tasks import async_log_activity
        async_log_activity.delay(data)
    except ImportError:
        logger.error("Async logging task not found")
    except Exception as e:
        logger.error(f"Async dispatch failed: {str(e)}")