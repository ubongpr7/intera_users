from django.db import models
from django.utils.translation import gettext_lazy as _
from cities_light.models import Country, Region, SubRegion,City

from mptt.models import MPTTModel, TreeForeignKey
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.conf import settings
from django_countries.fields import CountryField
from mainapps.common.validators import validate_city, validate_city_belongs_to_sub_region, validate_country, validate_postal_code, validate_region, validate_region_belongs_to_country, validate_sub_region
from mainapps.content_type_linking_models.models import GenericModel
User= settings.AUTH_USER_MODEL
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

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
        


class Attribute(models.Model):
    name = models.CharField(max_length=255)
    def __str__(self):
        return self.name

class Value(models.Model):
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)
    class Meta:
        unique_together = ('attribute', 'value')
    def __str__(self):
        return f'{self.value } {self.attribute}'

class Unit(models.Model):
    class DimensionType(models.TextChoices):
        MASS = 'mass', _('Mass')
        VOLUME = 'volume', _('Volume')
        LENGTH = 'length', _('Length')
        PIECE = 'piece', _('Piece')
        TIME = 'time', _('Time')
        CUSTOM = 'custom', _('Custom')

    dimension_type = models.CharField(
        max_length=50,
        choices=DimensionType.choices,
        default=DimensionType.CUSTOM,
        verbose_name=_('Dimension Category'),
        help_text=_('Type of measurement this unit belongs to')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Unit Name'),
        help_text=_('Full name of the unit (e.g., Kilogram)')
    )
    abbreviated_name = models.CharField(
        max_length=10,
        null=True,
        verbose_name=_('Abbreviation'),
        help_text=_('Standard short form (e.g., kg, L, m)'),
        validators=[
            RegexValidator(
                regex='^[A-Za-z]+$',
                message='Abbreviation can only contain letters',
                code='invalid_abbreviation'
            )
        ]
    )
    base_unit = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Base Unit'),
        help_text=_('Reference to base unit for conversions')
    )
    conversion_factor = models.DecimalField(
        max_digits=30,
        decimal_places=8,
        default=1.0,
        help_text=_('Conversion factor to base unit')
    )

    class Meta:
        ordering=['id']
        constraints = [
            models.UniqueConstraint(
                fields=['dimension_type', 'name'],
                name='unique_unit_per_dimension'
            ),
            models.UniqueConstraint(
                fields=['abbreviated_name', 'dimension_type'],
                name='unique_abbreviation_per_dimension'
            )
        ]
        indexes = [
            models.Index(fields=['dimension_type', 'name']),
            models.Index(fields=['abbreviated_name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.abbreviated_name}) - {self.get_dimension_type_display()}"

    def clean(self):
        """Add validation logic for conversion factors"""
        if self.base_unit and self.base_unit.dimension_type != self.dimension_type:
            raise ValidationError(_("Base unit must be of the same dimension type"))
        
        if self.base_unit and self.conversion_factor <= 0:
            raise ValidationError(_("Conversion factor must be a positive number"))   

class AttributeStore(GenericModel):
    attributes= models.JSONField(default=dict)
    def __str__(self):
        return self.attributes


from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

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

registerable_models=[Attribute,Value,Unit,AttributeStore,TypeOf]

