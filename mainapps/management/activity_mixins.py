# mixins.py
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from .models_activity.activity_logger import log_user_activity
from .models_activity.changes import get_field_changes

from .models import ActivityLog  

class ActivityTrackingMixin:
    """
    Mixin to log user activities for CRUD operations in ModelViewSets
    """
    
    def log_activity(self, user, action, instance, details):
        """
        Helper method to create activity log
        """
        model_name = instance.__class__.__name__
        object_id = instance.pk
        
        # Create log entry
        # ActivityLog.objects.create(
        #     user=user,
        #     action=action,
        #     model_name=model_name,
        #     object_id=object_id,
        #     details=details
        # )
        log_user_activity(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            details=details,
            instance=instance,
            async_log=True
        )
    def get_request_metadata(self, request):
        """Extracts common request metadata"""
        return {
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        }
    
    def create(self, request, *args, **kwargs):
        # Call the original create method
        response = super().create(request, *args, **kwargs)
        
        # Only log if creation was successful (HTTP 201)
        if response.status_code == status.HTTP_201_CREATED:
            instance = self.get_queryset().get(pk=response.data['id'])
            
            # Log creation activity
            metadata = self.get_request_metadata(request)
            metadata['initial_data'] = request.data
            metadata['created_data'] = response.data
            
            self.log_activity(
                user=request.user,
                action='CREATE',
                instance=instance,
                details=metadata
            )
        
        return response
    
    def update(self, request, *args, **kwargs):
        # Get instance before update
        instance = self.get_object()
        old_data = self.get_serializer(instance).data
        
        # Call the original update method
        response = super().update(request, *args, **kwargs)
        
        # Only log if update was successful (HTTP 200)
        if response.status_code == status.HTTP_200_OK:
            # Get updated instance
            updated_instance = self.get_object()
            
            # Log update activity
            metadata = self.get_request_metadata(request)
            metadata['changes'] = get_field_changes(old_data, response.data)
            
            self.log_activity(
                user=request.user,
                action='UPDATE',
                instance=updated_instance,
                details=metadata
            )
        
        return response
    
    def destroy(self, request, *args, **kwargs):
        # Get instance before deletion
        instance = self.get_object()
        deleted_data = self.get_serializer(instance).data
        
        # Call the original destroy method
        response = super().destroy(request, *args, **kwargs)
        
        # Only log if deletion was successful (HTTP 204)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            # Log deletion activity
            metadata = self.get_request_metadata(request)
            metadata['deleted_data'] = deleted_data
            
            self.log_activity(
                user=request.user,
                action='DELETE',
                instance=instance,
                details=metadata
            )
        
        return response