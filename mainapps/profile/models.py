import os
import secrets
import string
import uuid
from cryptography.fernet import Fernet
from django.db import models
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as __
from django.contrib.contenttypes.fields import GenericRelation

from mainapps.common.models import Address, Attachment
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
    profile = models.ForeignKey(
        'CompanyProfile',
        on_delete=models.CASCADE,
        related_name='addresses',
        null=True,
        blank=True
    )

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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_companies',
        blank=True, 
        # editable=False

    )
    company_code = models.CharField(
        max_length=15,
        unique=True,
        db_index=True,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_("Company Code"),
        help_text=_("Unique company login code used for tenant-scoped authentication."),
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

    @staticmethod
    def generate_company_code(length: int = 12) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def save(self, *args, **kwargs):
        if not self.company_code:
            while True:
                candidate = self.generate_company_code()
                if not CompanyProfile.objects.filter(company_code=candidate).exists():
                    self.company_code = candidate
                    break
        super().save(*args, **kwargs)

    def get_staff_roles(self):
        return StaffRole.objects.filter(profile=self)

    def get_staff_groups(self):
        return StaffGroup.objects.filter(profile=self)

    def staff_groups(self):
        return self.get_staff_groups()

    def get_membership_for_user(self, user):
        return self.memberships.filter(user=user, is_active=True).first()

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

    profile = models.ForeignKey(
        CompanyProfile, 
        on_delete=models.SET_NULL,
        null=True,editable=False, 
        related_name="%(class)s_set"
    )

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
    is_active = models.BooleanField(default=True)
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
    is_active = models.BooleanField(default=True)
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
    


class Policy(ProfileMixin):
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

    profile = models.ForeignKey(
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
    base_url = models.CharField(max_length=500, blank=True, null=True)

class ModelVersion(models.Model):
    llm = models.ForeignKey(LLMModel, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=255,)

    @property
    def provider(self):
        return self.llm.provider
    def __str__(self):
        return f"{self.model_name} - {self.provider}"
FERNET_KEY = os.getenv("FERNET_KEY")


def _build_cipher():
    if not FERNET_KEY:
        return None
    try:
        return Fernet(FERNET_KEY)
    except Exception as exc:
        raise ImproperlyConfigured("FERNET_KEY is invalid. Use a valid Fernet key.") from exc


cipher = _build_cipher()


def _is_encrypted_secret(value):
    return isinstance(value, str) and value.startswith("gAAAA")


def _encrypt_secret(value):
    if not value or _is_encrypted_secret(value):
        return value
    if cipher is None:
        raise ImproperlyConfigured("FERNET_KEY must be set before storing ProfileAgent secrets.")
    return cipher.encrypt(value.encode()).decode()


def _decrypt_secret(value):
    if not value:
        return ""
    if cipher is None:
        return value
    try:
        return cipher.decrypt(value.encode()).decode()
    except Exception:
        return value

class ProfileAgent(models.Model):
    profile = models.OneToOneField(CompanyProfile, related_name='agent', on_delete=models.CASCADE)
    name= models.CharField(max_length=255,)
    api_key= models.CharField(max_length=1000,)
    tavily_api_key = models.CharField(max_length=1000,)
    base_url = models.CharField(max_length=500, blank=True, null=True)
    version = models.ForeignKey(ModelVersion,on_delete=models.CASCADE)
    special_instruction = models.TextField(blank=True)
    system_instruction = models.TextField(blank=True)
    assistant_instruction = models.TextField(blank=True)
    # def set_sensitive_data(self, raw_data):
    #     encrypted_data = cipher.encrypt(raw_data.encode())
    #     self.encrypted_field = encrypted_data.decode()

    # def get_sensitive_data(self):
    #     decrypted_data = cipher.decrypt(self.encrypted_field.encode())
    #     return decrypted_data.decode()

    @property
    def provider(self):
        return self.version.provider
    @property
    def model_name(self):
        return self.version.model_name

    @property
    def effective_base_url(self):
        override = (self.base_url or "").strip()
        if override:
            return override
        provider_default = getattr(self.version.llm, "base_url", None)
        return (provider_default or "").strip()

    @property
    def decrypted_api_key(self):
        return _decrypt_secret(self.api_key)

    @property
    def decrypted_tavily_api_key(self):
        return _decrypt_secret(self.tavily_api_key)

    def save(self, *args, **kwargs):
        self.api_key = _encrypt_secret(self.api_key)
        self.tavily_api_key = _encrypt_secret(self.tavily_api_key)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Agent {self.name} - {self.model_name} - {self.provider} for {self.profile}"
        
class CompanyMembership(models.Model):
    class MembershipRole(models.TextChoices):
        OWNER = "owner", _("Owner")
        ADMIN = "admin", _("Admin")
        MEMBER = "member", _("Member")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )
    profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="company_memberships_invited",
        null=True,
        blank=True,
    )
    custom_permissions = models.ManyToManyField(
        CustomUserPermission,
        related_name="company_memberships",
        blank=True,
    )
    joined_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "profile")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["profile", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.profile_id}:{self.role}"


def generate_company_invitation_code():
    return secrets.token_urlsafe(18)[:24]


class CompanyInvitation(models.Model):
    class InvitationStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        DECLINED = "declined", _("Declined")
        EXPIRED = "expired", _("Expired")
        REVOKED = "revoked", _("Revoked")

    profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(
        max_length=20,
        choices=CompanyMembership.MembershipRole.choices,
        default=CompanyMembership.MembershipRole.MEMBER,
    )
    invitation_code = models.CharField(
        max_length=100,
        unique=True,
        default=generate_company_invitation_code,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="company_invitations_sent",
        null=True,
        blank=True,
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="company_invitations_accepted",
        null=True,
        blank=True,
    )
    invitation_message = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "status"]),
            models.Index(fields=["profile", "status"]),
            models.Index(fields=["invitation_code"]),
            models.Index(fields=["expires_at", "status"]),
        ]

    def __str__(self):
        return f"{self.profile_id}:{self.email}:{self.status}"


registerable_models = [
    CompanyProfile,
    PrescriptionFillingPolicies,
    StaffRoleAssignment,
    StaffRole,
    StaffGroup,
    CompanyProfileAddress,
    ProfileAgent,
    LLMModel,
    ModelVersion,
    CompanyMembership,
    CompanyInvitation,
]
