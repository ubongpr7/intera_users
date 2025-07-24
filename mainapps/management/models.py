from django.db import models
import uuid 
from django.conf import settings
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as __
from django.contrib.contenttypes.fields import GenericRelation

from mainapps.common.models import Address, Attachment
from django.utils import timezone
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
class Industry(models.TextChoices):
    MANUFACTURING = 'Manufacturing', _('Manufacturing')
    RETAIL = 'Retail', _('Retail')
    WHOLESALE = 'Wholesale', _('Wholesale')
    LOGISTICS = 'Logistics', _('Logistics')
    HEALTHCARE = 'Healthcare', _('Healthcare')
    FOOD_AND_BEVERAGE = 'Food & Beverage', _('Food & Beverage')
    TECHNOLOGY = 'Technology', _('Technology')
    CONSTRUCTION = 'Construction', _('Construction')
    PHARMACEUTICAL = 'Pharmaceutical', _('Pharmaceutical')
    AUTOMOTIVE = 'Automotive', _('Automotive')
    OTHER = 'Other', _('Other')

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
        # editable=False

    )
    name = models.CharField(
        max_length=100,
        blank=False,
        # unique=True,
        null=True,
        verbose_name=_('Company name'),
    )
    
    industry = models.CharField(
        max_length=50,
        choices=Industry.choices,
        blank=True,
        null=True,
        verbose_name=_('Industry'),
        help_text=_('Industry in which the company operates (optional)'),
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
    

    currency=models.CharField(
        max_length=23,
        null=True,
        blank=True
    )


    headquarters_address = models.ForeignKey(
        CompanyProfileAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    def get_staff_roles(self):
        return StaffRole.objects.filter(profile=self)
    def staff_groups(self):
        return StaffGroup.objects.filter(profile=self)
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
    class Meta:
        unique_together=('profile','name')

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


class RecallPolicy(models.Model):
    """Model for product recall policies"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        'CompanyProfile', 
        on_delete=models.CASCADE, 
        related_name='recall_policies'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    severity_levels = models.JSONField(
        default=list,
        help_text="List of severity levels and their descriptions"
    )
    notification_template = models.TextField(
        blank=True,
        help_text="Template for recall notifications"
    )
    contact_information = models.JSONField(
        default=dict,
        help_text="Contact information for recall management"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_recall_policies'
    )
    
    def __str__(self):
        return f"{self.name} - {self.profile.name}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Recall Policy"
        verbose_name_plural = "Recall Policies"

class ReorderStrategy(models.Model):
    """Model for inventory reorder strategies"""
    STRATEGY_CHOICES = [
        ('fixed', 'Fixed Quantity'),
        ('economic_order_quantity', 'Economic Order Quantity'),
        ('min_max', 'Min-Max'),
        ('periodic', 'Periodic Review'),
        ('just_in_time', 'Just-in-Time'),
        ('custom', 'Custom')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        'CompanyProfile', 
        on_delete=models.CASCADE, 
        related_name='reorder_strategies'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    strategy_type = models.CharField(
        max_length=30,
        choices=STRATEGY_CHOICES,
        default='fixed'
    )
    parameters = models.JSONField(
        default=dict,
        help_text="Parameters specific to the strategy type"
    )
    applies_to_categories = models.CharField(
        blank=True,
        max_length=255,
        help_text="Comma-separated list of inventory categories this strategy applies to",
        null=True
        )
    applies_to_all = models.BooleanField(
        default=False,
        help_text="If true, applies to all inventory items"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_reorder_strategies'
    )
    
    def __str__(self):
        return f"{self.name} ({self.get_strategy_type_display()}) - {self.profile.name}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Reorder Strategy"
        verbose_name_plural = "Reorder Strategies"

class InventoryPolicy(models.Model):
    """Model for general inventory management policies"""
    POLICY_TYPE_CHOICES = [
        ('expiry', 'Expiry Management'),
        ('quality', 'Quality Control'),
        ('storage', 'Storage Requirements'),
        ('counting', 'Inventory Counting'),
        ('valuation', 'Inventory Valuation'),
        ('other', 'Other')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        'CompanyProfile', 
        on_delete=models.CASCADE, 
        related_name='inventory_policies'
    )
    name = models.CharField(max_length=100)
    description = models.TextField()
    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPE_CHOICES,
        default='other'
    )
    details = models.JSONField(
        default=dict,
        help_text="Detailed policy configuration"
    )
    applies_to_categories = models.CharField(
        blank=True,
        max_length=255,
        help_text="Comma-separated list of inventory categories this policy applies to",
        null=True
    )

    applies_to_all = models.BooleanField(
        default=False,
        help_text="If true, applies to all inventory items"
    )
    effective_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_inventory_policies'
    )
    
    def __str__(self):
        return f"{self.name} ({self.get_policy_type_display()}) - {self.profile.name}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inventory Policy"
        verbose_name_plural = "Inventory Policies"

class LLMProviderChoices(models.TextChoices):
    gpt= ('chatgpt', 'Chat GPT')
    gemini = ('gemini','Gemini')
    grok = ('grok', 'Grok')

class LLMModel(models.Model):
    provider = models.CharField(max_length=255, choices=LLMProviderChoices.choices)

class ModelVersion(models.Model):
    llm = models.ForeignKey(LLMModel, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=255,)

    @property
    def provider(self):
        return self.llm.provider

class ProfileAgent(models.Model):
    profile = models.OneToOneField(CompanyProfile, related_name='agent', on_delete=models.CASCADE)
    name= models.CharField(max_length=255,)
    api_key= models.CharField(max_length=1000,)
    tavily_api_key = models.CharField(max_length=1000,)
    version = models.ForeignKey(ModelVersion,on_delete=models.CASCADE)
    special_instruction = models.TextField(blank=True)
    system_instruction = models.TextField(blank=True)
    assistant_instruction = models.TextField(blank=True)

    @property
    def provider(self):
        return self.version.provider
    @property
    def model_name(self):
        return self.version.model_name
    def __str__(self):
        return f"Agent {self.name} - {self.model_name} - {self.provider} for {self.profile}"
        
registerable_models=[CompanyProfile,PrescriptionFillingPolicies,ActivityLog,StaffRoleAssignment,StaffRole,StaffGroup,CompanyProfileAddress,ProfileAgent,LLMModel,ModelVersion]    