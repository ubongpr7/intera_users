from django.db import models
from django.utils.translation import gettext_lazy as _
from cities_light.models import Country, Region, SubRegion,City

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from mptt.models import MPTTModel, TreeForeignKey
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.conf import settings
from mainapps.common.validators import validate_city, validate_city_belongs_to_sub_region, validate_country, validate_postal_code, validate_region, validate_region_belongs_to_country, validate_sub_region
User= settings.AUTH_USER_MODEL
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

class Address(models.Model):

    class Meta:
        abstract= True

    
    country = models.ForeignKey(
        Country, 
        on_delete=models.CASCADE,
        verbose_name=_('Country'),
        null=True,
    )
    region = models.ForeignKey(
        Region, 
        on_delete=models.CASCADE,
        verbose_name=_('Region/State'),
        null=True,
    )
    subregion = models.ForeignKey(
        SubRegion, 
        on_delete=models.CASCADE,
        verbose_name=_('Sub region/LGA'),
        null=True,
    )
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        verbose_name=_('City/Town'),
        null=True,
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
        validators=[validate_postal_code]
    )

    def __str__(self):
        return f'{self.street}, {self.city}, {self.region}, {self.country}'
    def clean(self):
        if self.country:
            validate_country(self.country.id)
            if self.region:
                validate_region(self.region.id)
                if self.subregion:
                    validate_sub_region(self.subregion.id)
                    if self.city:
                        validate_city(self.city.id)
                        validate_region_belongs_to_country(self.region.id, self.country.id)
                        validate_city_belongs_to_sub_region(self.city.id, self.subregion.id)

class Currency(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=10, unique=True)
    def __str__(self):
        return f"{self.code}"
        

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




class ModelChoice(models.TextChoices):
    inventory='inventory','Inventory'
    stockitem='stock_item',"Stock item"
    company='company',"Company"
    policy='policy',"Policy"
    industry='industry',"Industry"

class TypeOf(MPTTModel):

    name = models.CharField(
        max_length=200, 
        # unique=True, 
        help_text='It must be unique', 
        verbose_name='Type'
    )
    which_model=models.CharField(max_length=30,choices=ModelChoice.choices,)
    slug = models.SlugField(max_length=230, editable=False,)
    is_active = models.BooleanField(default=True)
    parent = TreeForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        null=True,
        blank=True
    )
    description=models.TextField(blank=True,null=True)

    class MPTTMeta:

        order_insertion_by = ["parent","name"]

    class Meta:


        verbose_name_plural = _("Types of Instances")
        constraints=[
            models.UniqueConstraint(
                fields=[
                    'name',
                    'which_model'
                ],
                name='unique_type_name_which_model'
            )
        ]




    def save(self, *args, **kwargs):

        self.slug = f"{get_random_string(6)}{slugify(self.name)}-{self.pk}-{get_random_string(5)}"

        super(TypeOf, self).save(*args, **kwargs)


    def __str__(self):

        return self.name




