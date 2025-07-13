from django.db import models
from django.utils.translation import gettext_lazy as _

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from mptt.models import MPTTModel, TreeForeignKey
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.conf import settings
User= settings.AUTH_USER_MODEL
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

class Address(models.Model):

    
    country = models.CharField(
        max_length=255,
        verbose_name=_('Country'),
        help_text=_('Country of the address'),
        null=True,
        blank=True
    )
    region = models.CharField(
        max_length=255,
        verbose_name=_('Region/State'),
        help_text=_('Region or state within the country'),
        null=True,
        blank=True
    )
    subregion = models.CharField(
        max_length=255,
        verbose_name=_('Subregion/Province'),
        help_text=_('Subregion or province within the region'),
        null=True,
        blank=True
    )
    city = models.CharField(
        max_length=255,
        verbose_name=_('City'),
        help_text=_('City of the address'),
        null=True,
        blank=True
    )
    apt_number = models.PositiveIntegerField(
        verbose_name=_('Apartment number'),
        null=True,
        blank=True
    )
    street_number = models.PositiveIntegerField(
        verbose_name=_('Street number'),
        null=True,
        blank=True
    )
    street = models.CharField(max_length=255,blank=False,null=True)

    postal_code = models.CharField(
        max_length=10,
        verbose_name=_('Postal code'),
        help_text=_('Postal code'),
        blank=True,
        null=True,
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name=_('Latitude'),
        help_text=_('Geographical latitude of the address'),
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        verbose_name=_('Longitude'),
        help_text=_('Geographical longitude of the address'),
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.street}, {self.city}, {self.region}, {self.country}'

def attachment_upload_path(instance, filename):
    return f'attachments/{instance.attachment.content_type.model}/{instance.attachment.object_id}/{instance.attachment.id}/{instance.id}/{filename}'

class Attachment(models.Model):
    FILE_TYPES = (
        ('IMAGE', 'Image'),
        ('DOC', 'Document'),
        ('OTHER', 'Other'),
    )
    
    PURPOSES = (
        ('MAIN_IMAGE', 'Main Product Image'),
        ('GALLERY', 'Gallery Image'),
        ('MANUAL', 'Product Manual'),
        ('SPEC', 'Specification Sheet'),
    )
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    file = models.FileField(
        upload_to=attachment_upload_path,
        null=True,
        blank=True,
       
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    purpose = models.CharField(max_length=20, choices=PURPOSES, default='GALLERY')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")

    def __str__(self):
        return f"{self.get_file_type_display()} for {self.content_object}"



