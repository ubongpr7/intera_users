from django.db import models
from django.utils.translation import gettext_lazy as _

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from datetime import datetime


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
    class Meta:
        abstract = True


    def __str__(self):
        return f'{self.street}, {self.city}, {self.region}, {self.country}'

def attachment_upload_path(instance, filename):
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    return f"attachments/{instance.attachment.content_type.model}/{instance.attachment.object_id}/{timestamp}-{filename}"
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


class Unit(models.Model):
    class DimensionType(models.TextChoices):
        MASS = "MASS", _("Mass")
        VOLUME = "VOLUME", _("Volume")
        LENGTH = "LENGTH", _("Length")
        PIECE = "PIECE", _("Piece")
        TIME = "TIME", _("Time")
        CUSTOM = "CUSTOM", _("Custom")

    name = models.CharField(max_length=100)
    abbreviated_name = models.CharField(max_length=20)
    dimension_type = models.CharField(max_length=20, choices=DimensionType.choices)
    base_unit = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_units",
    )
    conversion_factor = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["dimension_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dimension_type", "name"],
                name="common_unit_dimension_name_unique",
            )
        ]
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")

    def __str__(self):
        return f"{self.name} ({self.dimension_type})"


