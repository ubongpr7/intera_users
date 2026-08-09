import os
import random
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
)


def get_upload_path(instance, filename):
    return os.path.join('images', 'avatar', str(instance.pk or "unknown"), filename)




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
    date_of_birth = models.DateField(
        verbose_name='Date Of Birth',
        help_text='You must be above 18 years of age.',
        blank=True,
        null=True,
    )
    profile = models.ForeignKey(
        'profile.CompanyProfile',
        on_delete=models.CASCADE,
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
        try:
            return self.picture.url
        except:
            no_picture = settings.MEDIA_URL + 'default.png'
            return no_picture


    def delete(self, *args, **kwargs):
        if self.picture.url != settings.MEDIA_URL + 'default.png':
            self.picture.delete()
        super().delete(*args, **kwargs)

    @property
    def role(self):
        assignment = self.roles.filter(is_active=True).select_related("role").first()
        return assignment.role.name if assignment else None


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
    
