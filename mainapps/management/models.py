from django.db import models
import uuid 
from django.conf import settings
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as __
from django.db.models import UniqueConstraint
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.text import slugify

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.signing import Signer
from django.contrib.auth.models import Permission
from mainapps.common.models import Address, Country, Currency, TypeOf,Attachment
from mainapps.common.settings import  DEFAULT_CURRENCY_CODE, currency_code_mappings
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone

from mainapps.permit.models import CustomUserPermission

class RecallPolicies(models.TextChoices):
    REMOVE = "0", _("Remove from Stock")
    NOTIFY_CUSTOMERS = "1", _("Notify Customers")
    REPLACE_PRODUCT = "3", _("Replace Item")
    DESTROY = "4", _("Destroy Item")
    REPAIR = "5", _("Repair Item")
class ReorderStrategies(models.TextChoices):
    FIXED_QUANTITY = "FQ", _("Fixed Quantity")
    FIXED_INTERVAL = "FI", _("Fixed Interval")
    DYNAMIC = "DY", _("Demand-Based")
class ExpirePolicies(models.TextChoices):
    REMOVE = "0", _("Dispose of Stock")
    RETURN_MANUFACTURER = "1", _("Return to Manufacturer")
class NearExpiryActions(models.TextChoices):
    DISCOUNT = "DISCOUNT", _("Sell at Discount")
    DONATE = "DONATE", _("Donate to Charity")
    DESTROY = "DESTROY", _("Destroy Immediately")
    RETURN = "RETURN", _("Return to Supplier")

class ForecastMethods(models.TextChoices):
    SIMPLE_AVERAGE = "SA", _("Simple Average")
    MOVING_AVERAGE = "MA", _("Moving Average")
    EXP_SMOOTHING = "ES", _("Exponential Smoothing")


# Create your models here.
class CompanyProfileAddress(Address):
    pass

class CompanyProfile(models.Model):
    class Meta:
        """Metaclass defines extra model options."""

        ordering = ['name']

        verbose_name_plural = 'Company Profile'

    po_sequence = models.PositiveIntegerField(default=0)
    inventory_sequence = models.PositiveIntegerField(default=0)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        related_name='company',
        blank=True, 
        editable=False

    )
    name = models.CharField(
        max_length=100,
        blank=False,
        # unique=True,
        verbose_name=_('Company name'),
    )
    
    industry=models.ForeignKey(
        TypeOf,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        limit_choices_to={'which_model':'industry'}

    )

    description = models.CharField(
        max_length=1000,
        verbose_name=_('Company description'),
        help_text=_('Briefly describe the company'),
        blank=True,
        null=True,
    )
    founded_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Founded Date'
    )

    employees_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Number of Employees'
    )

    tax_id = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Tax ID/VAT Number',
        null=True
    )


    website = models.URLField(
        blank=True, verbose_name=_('Website'), help_text=_('Company website URL (optional)')
    )

    linkedin = models.URLField(
    blank=True,
    verbose_name='LinkedIn Profile',
    null=True
    )
 
    twitter = models.URLField(
        blank=True,
        verbose_name='Twitter Profile',
        null=True
    )

    instagram = models.URLField(
        blank=True,
        verbose_name='Instagram Profile',
        null=True
        )

    facebook = models.URLField(
        blank=True,
        verbose_name='Facebook Profile',
        null=True
    
    )

    other_link = models.URLField(
        blank=True,
        verbose_name=_('Link/Website'),
        help_text=_('Link to external company information or profile'),
    )

    phone = models.CharField(
        max_length=20,
        verbose_name=_('Phone number'),
        blank=True,
        help_text=_('Contact phone number (optional)'),
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Email'),
        help_text=_('Contact email address (optional)'),
    )
    

    currency=models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )


    headquarters_address = models.ForeignKey(
        CompanyProfileAddress,
        on_delete=models.SET_NULL,
        null=True,
    )

    
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Verified Company'
    )

    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Verification Date'
    )

    attachment= GenericRelation(Attachment,  related_query_name='companies')
    
    created_at = models.DateTimeField(default=timezone.now)

    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.owner:

            return f'{self.name} -> {self.id} {self.owner.email}' 
        return f'{self.name } -> {self.id}'





class ProfileManager(models.Manager):
    """
    - Custom manager for the Inventory model.
    - Provides methods for querying inventories.
    """

    def for_profile(self, profile):
        
        return self.get_queryset().filter(profile=profile)


class ProfileMixin(models.Model):
    """
    Abstract model providing a common base for models associated with an inventory.

    - Attributes:
        - inventory (Inventory): The inventory to which the model belongs.

    - Manager:
        - objects (InventoryManager): Custom manager for querying objects based on inventory.
    """

    profile = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL,null=True)

    objects = ProfileManager()

    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """
        Override the save method to perform additional actions when saving.

        Args:
            - *args: Additional positional arguments.
            - **kwargs: Additional keyword arguments.
        """
        super().save(*args, **kwargs)


class StaffGroup(ProfileMixin):
    name = models.CharField(max_length=255)
    permissions = models.ManyToManyField(
        CustomUserPermission,
        related_name='groups',
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='groups_created',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True, related_name='staff_groups')
    description = models.TextField(null=True, blank=True)
    def __str__(self):
        return self.name
    
class StaffRole(ProfileMixin):
    name = models.CharField(max_length=255)
    permissions = models.ManyToManyField(
        CustomUserPermission,
        related_name='roles',
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rolse_created',
        editable=False,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

    
class StaffRoleAssignment(ProfileMixin):
    """Manages temporal user-role assignments"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='roles')
    role = models.ForeignKey(StaffRole, on_delete=models.CASCADE,related_name='assignments')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_roles',
        editable=False,
        help_text='User who assigned the role'
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ('user', 'role',)
        ordering = ['-start_date']

    def save(self, *args, **kwargs):
        if self.is_active:
            StaffRoleAssignment.objects.filter(
                user=self.user, 
                role=self.role,
                is_active=True
            ).delete()
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")
        if self.end_date and self.end_date < timezone.now():
            raise ValueError("End date cannot be in the past.")
        if self.start_date and self.start_date < timezone.now():
            self.start_date = timezone.now()
        
        super().save(*args, **kwargs)

    @property
    def is_current(self):
        now = timezone.now()
        if self.end_date:
            return self.start_date <= now <= self.end_date
        return self.start_date <= now

    def __str__(self):
        return f"{self.user} → {self.role} ({'active' if self.is_active else 'inactive'})"
    


class Policy(models.Model):
    name = models.CharField(
        max_length=100,
        blank=False,
        unique=True,
        verbose_name=_('Policy name'),
    )

    details = models.TextField(
        blank=False,
        unique=True,
        verbose_name=_('Details of the policy'),
    )

    company=models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        editable=False

    )
    effective_date=models.DateField(
        null=True,
    )
    expiration_date=models.DateField(
        null=True,
    )
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        abstract=True


class PrescriptionFillingPolicies(Policy):
    validity_period=models.IntegerField(
        default=5,
        help_text='Prescription is valid before how many days',
    )
    quantitity_limit=models.IntegerField(
    )
    refills_allowed=models.IntegerField(
        # help_text='Prescription is valid before how many days',
    )



class ActivityLog(ProfileMixin):
    """
    Tracks all user activities
    """
    ACTION_CHOICES = [
        ('CREATE', 'Creation'),
        ('UPDATE', 'Modification'),
        ('DELETE', 'Deletion'),
        ('APPROVE', 'Approval'),
        ('CANCEL', 'Cancellation'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=255)
    object_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} {self.object_id}"
    
registerable_models=[CompanyProfile,PrescriptionFillingPolicies,ActivityLog,StaffRoleAssignment,StaffRole,StaffGroup,CompanyProfileAddress]    