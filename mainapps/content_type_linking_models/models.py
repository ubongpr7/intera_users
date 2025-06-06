from datetime import timezone
from django.contrib.contenttypes.fields import GenericForeignKey,GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.translation import gettext_lazy as _

from django.conf import settings
import uuid
User= settings.AUTH_USER_MODEL

class UUIDBaseModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
        help_text=_("Unique identifier for the model instance.")
    )
    
    class Meta:
        abstract=True
class GenericModel(models.Model):
    """
    Abstract base class for models with GenericForeignKey.

    This abstract base class provides fields to link to any other model using a GenericForeignKey.
    It includes fields for content type, object ID, and a field to specify the target model.

    Fields:
    - content_type: ForeignKey to ContentType model representing the type of the linked object.
    - object_id: PositiveIntegerField representing the ID of the linked object.
    - content_object: GenericForeignKey to represent the linked object.
    - created_at: DateTime field representing the timestamp when the like was created.
    - updated_at: DateTime field representing the timestamp when the comment was last updated.

    Methods:
    - __str__: Returns a string representation of the model instance.
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name='Content Type',
        help_text='The content type of the linked object.'
    )
    object_id = models.PositiveIntegerField(
        verbose_name='Object ID',
        help_text='The ID of the linked object.'
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        """
        String representation of the model instance.
        
        Returns:
            str: A string representing the linked object using content type and object ID.
        """
        return f"Instance for {self.content_type.model} ({self.object_id})"

    # def save(self, *args, **kwargs):
    #     """
    #     Override the save method to update updated_at field.
    #     """
    #     if not self.pk:
    #         # This is a new instance, set the created_at timestamp
    #         self.created_at = timezone.now()
    #     # Always update the updated_at timestamp
    #     self.updated_at = timezone.now()
    #     super().save(*args, **kwargs)


class UserSubscription(models.Model):
    """
    Represents a user's subscription to an inventory.

    Attributes:
        - user (ForeignKey): The user subscribing to the inventory.
        - content_type (ForeignKey): The content type of the related object (Inventory, in this case).
        - object_id (PositiveIntegerField): The ID of the related object.
        - inventory (GenericForeignKey): Generic relation to the related inventory.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    inventory = GenericForeignKey('content_type', 'object_id')


class Notification(GenericModel):
    """
    Represents a notification for a user within an inventory.

    Attributes:
        - user (ForeignKey): The user receiving the notification.
        - content_type (ForeignKey): The content type of the related object (Inventory, in this case).
        - object_id (PositiveIntegerField): The ID of the related object.
        - inventory (GenericForeignKey): Generic relation to the related inventory.
        - message (TextField): The content of the notification message.
        - timestamp (DateTime): The date and time when the notification was created.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()


def attachment_upload_path(instance, filename):
    return f'attachments/{instance.attachment.content_type.model}/{instance.attachment.object_id}/{instance.attachment.id}/{instance.id}/{filename}'


class ContentTypeLink(models.Model):
    """
    Represents a link between two ContentType instances.

    Attributes:
        - content_type_1 (ForeignKey): The first content type in the link.
        - object_id_1 (PositiveIntegerField): The ID of the related object for the first content type.
        - content_object_1 (GenericForeignKey): Generic relation to the related object for the first content type.
        - content_type_2 (ForeignKey): The second content type in the link.
        - object_id_2 (PositiveIntegerField): The ID of the related object for the second content type.
        - content_object_2 (GenericForeignKey): Generic relation to the related object for the second content type.
    """
    content_type_1 = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='link_type_1')
    object_id_1 = models.PositiveIntegerField()
    content_object_1 = GenericForeignKey('content_type_1', 'object_id_1')

    content_type_2 = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='link_type_2')
    object_id_2 = models.PositiveIntegerField()
    content_object_2 = GenericForeignKey('content_type_2', 'object_id_2')

    def __str__(self):
        return f"{self.content_type_1} - {self.object_id_1} to {self.content_type_2} - {self.object_id_2}"

    class Meta:
        verbose_name = "Content Type Link"
        verbose_name_plural = "Content Type Links"



registerable_models=[UserSubscription,Notification,ContentTypeLink]
    