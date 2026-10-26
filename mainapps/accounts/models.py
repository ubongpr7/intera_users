import os
import random
import secrets
import string
import re
import hashlib
import uuid
from datetime import timedelta
from PIL import Image
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from mainapps.common.models import Address
from mainapps.permit.models import CustomUserPermission


class ResidentialAddress(Address):
    
    resident = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='residence',
        editable=False,
        null=True,
        blank=True
    ) 

PREFER_NOT_TO_SAY="not_to_mention"
SEX=(
    ("male",_("Male")),
    ("female",_("Female")),
    (PREFER_NOT_TO_SAY,_("Prefer not to mention")),
)


def get_upload_path(instance, filename):
    return os.path.join('images', 'avatar', str(instance.pk or "unknown"), filename)


def generate_referral_code():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(12))


def referral_code_from_email(email, *, exclude_user_id=None):
    """Prefer a memorable email-local-part code, then fall back safely."""
    local_part = str(email or '').split('@', 1)[0].upper()
    base = re.sub(r'[^A-Z0-9_-]', '', local_part)[:16] or 'REFERRAL'
    candidate = base
    existing_users = User.objects.filter(referral_code__iexact=candidate)
    if exclude_user_id is not None:
        existing_users = existing_users.exclude(pk=exclude_user_id)
    if not existing_users.exists() and not AffiliatePartner.objects.filter(code__iexact=candidate).exists():
        return candidate

    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        suffix = ''.join(secrets.choice(alphabet) for _ in range(5))
        candidate = f'{base[:10]}-{suffix}'[:16]
        existing_users = User.objects.filter(referral_code__iexact=candidate)
        if exclude_user_id is not None:
            existing_users = existing_users.exclude(pk=exclude_user_id)
        if not existing_users.exists() and not AffiliatePartner.objects.filter(code__iexact=candidate).exists():
            return candidate
    return generate_referral_code()


class AffiliatePartner(models.Model):
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True, default="", db_index=True)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    commission_rate = models.DecimalField(max_digits=6, decimal_places=5, default='0.05000')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_affiliate_partners',
    )
    account_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affiliate_partner_account',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.code})'


class AffiliatePartnerInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(AffiliatePartner, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="affiliate_partner_invitations")
    accepted_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="accepted_affiliate_invitations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("partner",), condition=Q(status="pending"), name="accounts_one_pending_affiliate_invite"),
        ]
        ordering = ("-created_at",)

    @staticmethod
    def normalize_email(value):
        return str(value or "").strip().lower()

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()




class CustomUserManager(BaseUserManager):
    def search(self, query=None):
        qs = self.get_queryset()
        if query is not None:
            or_lookup = (Q(email__icontains=query) | 
                            Q(first_name__icontains=query)| 
                            Q(last_name__icontains=query)| 
                            Q(email__icontains=query)
                        )
            qs = qs.filter(or_lookup).distinct() # distinct() is often necessary with Q lookups
        return qs

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault('referral_code', referral_code_from_email(email))
        user = self.model(email=email, **extra_fields)
        if not user.username:
            user.username = email
        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
            extra_fields.setdefault("is_staff", True)
            extra_fields.setdefault("is_superuser", True)

            if not extra_fields.get("is_staff"):
                raise ValueError("Superuser must have is_staff=True.")
            if not extra_fields.get("is_superuser"):
                raise ValueError("Superuser must have is_superuser=True.")

            user = self.create_user(email, password, **extra_fields)
            return user

class User(AbstractUser):
    phone = models.CharField(
        max_length=60, 
        blank=True, 
        null=True
    )
    
    picture = models.ImageField(
        upload_to='profile_pictures/%y/%m/%d/', 
        default='default.png', 
        null=True
    
        )
    
    email = models.EmailField(blank=False, null=False, unique=True, db_index=True)
    sex=models.CharField(
        max_length=20,
        choices=SEX,
        default=PREFER_NOT_TO_SAY,
        blank=True,
        null=True
    )
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_affiliate_marketer = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Affiliate partner account restricted from normal workspace and billing operations.',
    )
    date_of_birth = models.DateField(
        verbose_name='Date Of Birth',
        help_text='You must be above 18 years of age.',
        blank=True,
        null=True,
    )
    profile = models.ForeignKey(
        'profile.CompanyProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
        # editable=False
        
    )

    custom_permissions = models.ManyToManyField(
        CustomUserPermission,
        related_name='users',
        blank=True
    )
    mfa_secret = models.CharField(max_length=255, blank=True, null=True)
    mfa_enabled = models.BooleanField(default=False)
    has_setup_mfa = models.BooleanField(default=False)
    referral_code = models.CharField(
        max_length=16,
        unique=True,
        editable=False,
        default=generate_referral_code,
        db_index=True,
    )
    referral_commission_rate = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default='0.05000',
        help_text='Commission rate applied to subscription payments from direct referrals.',
    )
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users',
    )
    referred_by_affiliate_partner = models.ForeignKey(
        AffiliatePartner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users',
    )
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()
  
    def save(self, *args, **kwargs):
        if self.email and (not self.username or self.username != self.email):
            self.username = self.email
        super().save(*args, **kwargs)


        try:
            img = Image.open(self.picture.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.picture.path)
        except:
            pass


    @property
    def get_full_name(self):
        full_name = self.email
        if self.first_name and self.last_name:
            full_name = self.first_name + " " + self.last_name
        return full_name

    def __str__(self):
        return self.email

        

    def get_picture(self):
        # The default field value is a logical placeholder, not a guaranteed
        # object in production media storage. Do not emit a URL that can 404.
        if not self.picture or self.picture.name == 'default.png':
            return None
        try:
            if not self.picture.storage.exists(self.picture.name):
                return None
            return self.picture.url
        except (OSError, ValueError):
            return None

    def delete(self, *args, **kwargs):
        if self.picture and self.picture.name != 'default.png':
            self.picture.delete()
        super().delete(*args, **kwargs)

    @property
    def role(self):
        assignment = self.roles.filter(is_active=True).select_related("role").first()
        return assignment.role.name if assignment else None


class PlatformStaffInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="platform_staff_invitations")
    accepted_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="accepted_platform_staff_invitations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("email",), condition=Q(status="pending"), name="accounts_one_pending_platform_staff_invite"),
        ]
        ordering = ("-created_at",)

    @staticmethod
    def normalize_email(value):
        return str(value or "").strip().lower()

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


class ReferralPayout(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    referrer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='referral_payouts',
    )
    affiliate_partner = models.ForeignKey(
        AffiliatePartner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payouts',
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_payment_payouts',
    )
    commission_rate = models.DecimalField(max_digits=6, decimal_places=5, default='0.05000')
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payout_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    payment_reference = models.CharField(max_length=255, unique=True)
    payment_id = models.CharField(max_length=255, blank=True)
    profile_id = models.CharField(max_length=255, blank=True)
    plan_slug = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('referrer_user', 'status')),
            models.Index(fields=('referred_user',)),
        ]

    def __str__(self):
        owner = (
            self.referrer_user.email
            if self.referrer_user
            else self.affiliate_partner.name
            if self.affiliate_partner
            else 'Affiliate'
        )
        return f'{owner}: {self.payout_amount} {self.currency}'


class LegalConsent(models.Model):
    class ConsentType(models.TextChoices):
        TERMS = "terms", "Terms and Conditions"
        PRIVACY = "privacy", "Privacy Policy"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_consents",
    )
    consent_type = models.CharField(max_length=16, choices=ConsentType.choices)
    policy_version = models.CharField(max_length=64)
    accepted_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=1024, blank=True)
    source = models.CharField(max_length=32, default="signup")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "consent_type", "policy_version"),
                name="unique_user_legal_consent_version",
            )
        ]
        indexes = [models.Index(fields=("user", "consent_type"))]

    def __str__(self):
        return f"{self.user.email}: {self.get_consent_type_display()} {self.policy_version}"

class LinkedAccount(models.Model):
    platform=models.CharField(max_length=255)
    platform_user_id=models.UUIDField()
    linked_at=models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,related_name='linked_accounts')
    class Meta:
        unique_together=('platform','platform_user_id','user')

class VerificationCode(models.Model):
    EMAIL = "email"
    VERIFICATION_TYPES = (
        (EMAIL, "Email"),
    )
    CODE_TTL_MINUTES = 10
    MAX_ATTEMPTS = 5

    user=models.OneToOneField(User,on_delete=models.CASCADE)
    verification_type = models.CharField(max_length=32, choices=VERIFICATION_TYPES, default=EMAIL)
    code=models.CharField(max_length=6,blank=True)
    slug=models.SlugField(editable=False,blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    time_requested=models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    successful_attempts=models.IntegerField(default=0)
    total_attempts=models.IntegerField(default=0)

    def __str__(self):
        return self.code

    @staticmethod
    def generate_code(length=6):
        nums = [str(i) for i in range(10)]
        code_list = [random.choice(nums) for _ in range(length)]
        return "".join(code_list)

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES)

    def regenerate(self, save=True):
        self.code = self.generate_code()
        self.expires_at = self.default_expiry()
        self.total_attempts = 0
        self.successful_attempts = 0
        self.slug = self.user.email
        if save:
            self.save(update_fields=["code", "expires_at", "total_attempts", "successful_attempts", "slug", "time_requested"])
        return self

    def mark_failed_attempt(self):
        self.total_attempts += 1
        self.save(update_fields=["total_attempts", "time_requested"])

    def mark_successful_attempt(self):
        self.successful_attempts += 1
        self.save(update_fields=["successful_attempts", "time_requested"])

    def is_valid(self):
        if self.total_attempts >= self.MAX_ATTEMPTS:
            return False
        if not self.expires_at:
            return False
        return timezone.now() <= self.expires_at

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        if not self.slug and self.user_id:
            self.slug = self.user.email
        if not self.expires_at:
            self.expires_at = self.default_expiry()
        super().save(*args, **kwargs)
    
