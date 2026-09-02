from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone

from .models import User, VerificationCode
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as BaseTokenRefreshSerializer

from djoser.social.serializers import ProviderAuthSerializer
from mainapps.profile.models import CompanyMembership, CompanyProfile
from mainapps.permit.models import PlatformChoices
from mainapps.accounts.legal import record_signup_consents, validate_signup_consents
from mainapps.profile.support_access import (
    list_accessible_profile_contexts,
    resolve_profile_access,
)
from subapps.kafka.producers import build_actor, publish_support_access_workspace_entered
from .authorization_context import issue_authorization_context


def _resolve_referrer(attrs):
    code = (attrs.get('referral_code') or '').strip().upper()
    attrs['referral_code'] = code
    if not code:
        attrs['referrer_user'] = None
        return attrs
    referrer = User.objects.filter(referral_code__iexact=code).first()
    if referrer is None:
        raise serializers.ValidationError({'referral_code': 'Referral code is invalid.'})
    attrs['referrer_user'] = referrer
    return attrs


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    profile_id = serializers.IntegerField(required=False, write_only=True)
    company_code = serializers.CharField(required=False, write_only=True, allow_blank=True)
    support_access_grant_id = serializers.UUIDField(required=False, write_only=True)
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        required=False,
        write_only=True,
        default=PlatformChoices.INTERA_IMS,
    )

    @classmethod
    def _active_memberships(cls, user):
        return CompanyMembership.objects.filter(user=user, is_active=True).select_related("profile")

    @classmethod
    def _owned_profiles(cls, user):
        return CompanyProfile.objects.filter(owner=user)

    @classmethod
    def user_has_profile_access(cls, user, profile):
        return bool(resolve_profile_access(user, profile_id=getattr(profile, "id", None)).profile)

    @classmethod
    def list_accessible_profile_contexts(cls, user):
        return list_accessible_profile_contexts(user)

    @classmethod
    def list_accessible_profiles(cls, user):
        return [context.profile for context in cls.list_accessible_profile_contexts(user)]

    @staticmethod
    def _subscription_snapshot(profile):
        snapshot = getattr(profile, "subscription_snapshot", None) or {}
        return snapshot if isinstance(snapshot, dict) else {}

    @classmethod
    def _subscription_metadata(cls, profile):
        snapshot = cls._subscription_snapshot(profile)
        subscription = snapshot.get("subscription") or {}
        plan = subscription.get("plan") or {}
        return {
            "profile_id": snapshot.get("profile_id"),
            "application": snapshot.get("application"),
            "subscription": subscription,
            "plan": plan,
            "plan_features": snapshot.get("features") or {},
        }

    @classmethod
    def resolve_active_profile_access(
        cls,
        user,
        profile_id=None,
        company_code=None,
        support_access_grant_id=None,
    ):
        requested_profile = None
        if profile_id:
            requested_profile = CompanyProfile.objects.filter(id=profile_id).first()
            if not requested_profile:
                raise serializers.ValidationError({"profile_id": "Company profile not found."})
        elif company_code:
            requested_profile = CompanyProfile.objects.filter(company_code__iexact=company_code).first()
            if not requested_profile:
                raise serializers.ValidationError({"company_code": "Invalid company code."})

        access = resolve_profile_access(
            user,
            profile_id=profile_id,
            company_code=company_code,
            support_access_grant_id=support_access_grant_id,
        )
        if support_access_grant_id and not access.support_grant:
            raise serializers.ValidationError(
                {"support_access_grant_id": "Support access grant is invalid, expired, or revoked."}
            )
        if requested_profile and not access.profile:
            raise serializers.ValidationError(
                {"profile_id": "You do not have access to the requested company profile."}
            )
        return access

    @classmethod
    def resolve_active_profile(cls, user, profile_id=None, company_code=None, support_access_grant_id=None):
        return cls.resolve_active_profile_access(
            user,
            profile_id=profile_id,
            company_code=company_code,
            support_access_grant_id=support_access_grant_id,
        ).profile

    @classmethod
    def get_all_permissions(cls, user, profile=None, support_grant=None, platform=PlatformChoices.INTERA_IMS):
        if support_grant is not None:
            return support_grant.effective_permission_codenames()

        user_perms = set()
        user_perms.update(
            user.custom_permissions.filter(platform=platform).values_list("codename", flat=True)
        )
        if not profile:
            return sorted(user_perms)

        current_time = timezone.now()
        try:
            for assignment in user.roles.filter(
                Q(profile=profile) | Q(role__is_system=True, role__profile__isnull=True),
                is_active=True,
                role__platform=platform,
            ).select_related("role"):
                if assignment.end_date and assignment.end_date < current_time:
                    assignment.is_active = False
                    assignment.save(update_fields=["is_active"])
                    continue
                if assignment.start_date and assignment.start_date > current_time:
                    continue
                perms = assignment.role.permissions.all().values_list("codename", flat=True)
                user_perms.update(perms)
        except Exception:
            pass
        try:
            groups = user.staff_groups.filter(
                Q(profile=profile) | Q(is_system=True, profile__isnull=True),
                is_active=True,
                platform=platform,
            )
            for group in groups:
                user_perms.update(group.permissions.all().values_list("codename", flat=True))
        except Exception:
            pass

        membership = CompanyMembership.objects.filter(
            user=user,
            profile=profile,
            is_active=True,
        ).first()
        if membership:
            user_perms.update(
                membership.custom_permissions.filter(platform=platform).values_list("codename", flat=True)
            )

        return sorted(user_perms)

    @classmethod
    def _profile_payload(cls, profile, user, support_grant=None):
        if not profile:
            return None
        subscription_metadata = cls._subscription_metadata(profile)
        if support_grant is not None:
            role = support_grant.membership_role
            membership_id = None
        elif profile.owner_id == user.id:
            role = CompanyMembership.MembershipRole.OWNER
            membership_id = None
        else:
            membership = CompanyMembership.objects.filter(
                user=user,
                profile=profile,
                is_active=True,
            ).only("id", "role").first()
            role = membership.role if membership else None
            membership_id = str(membership.id) if membership else None
        return {
            "id": str(profile.id),
            "name": profile.name,
            "company_code": profile.company_code,
            "logo": profile.logo.url if getattr(profile, "logo", None) else None,
            "industry": profile.industry,
            "owner_id": str(profile.owner_id) if profile.owner_id else None,
            "currency": profile.currency,
            "role": role,
            "membership_id": membership_id,
            "support_access": support_grant is not None,
            "support_access_grant_id": str(support_grant.id) if support_grant else None,
            "support_access_expires_at": support_grant.expires_at.isoformat() if support_grant else None,
            "support_access_mode": support_grant.permission_mode if support_grant else None,
            "support_actor_type": "support" if support_grant else "workspace_member",
            "subscription_snapshot": cls._subscription_snapshot(profile),
            "subscription": subscription_metadata,
        }

    @classmethod
    def _apply_claims(cls, token, user, profile, support_grant=None, platform=PlatformChoices.INTERA_IMS):
        token["profile_id"] = str(profile.id) if profile else None
        token["company_code"] = profile.company_code if profile else None
        token["profile_industry"] = profile.industry if profile else None
        token["email"] = user.email
        token["is_staff"] = bool(user.is_staff)
        token["is_superuser"] = bool(user.is_superuser)
        token["mfa_enabled"] = bool(getattr(user, "mfa_enabled", False))
        token["has_setup_mfa"] = bool(getattr(user, "has_setup_mfa", False))
        token["owner_id"] = str(profile.owner_id) if profile and profile.owner_id else None
        token["platform"] = platform

        role = None
        if support_grant is not None:
            role = support_grant.membership_role
        elif profile:
            if profile.owner_id == user.id:
                role = CompanyMembership.MembershipRole.OWNER
            else:
                membership = CompanyMembership.objects.filter(
                    user=user,
                    profile=profile,
                    is_active=True,
                ).only("role").first()
                role = membership.role if membership else None
        token["membership_role"] = role
        token["support_access_grant_id"] = str(support_grant.id) if support_grant else None
        token["support_access_expires_at"] = (
            support_grant.expires_at.isoformat() if support_grant else None
        )
        token["support_access_scope"] = (
            support_grant.effective_permission_codenames() if support_grant else None
        )
        token["support_access_mode"] = support_grant.permission_mode if support_grant else None
        token["support_actor_type"] = "support" if support_grant else "workspace_member"

        token["mfa_verified"] = bool(getattr(user, "_jwt_mfa_verified", False))

    @classmethod
    def issue_tokens_for_profile(cls, user, profile, mfa_verified=False, support_grant=None, platform=PlatformChoices.INTERA_IMS):
        setattr(user, "_jwt_active_profile", profile)
        setattr(user, "_jwt_mfa_verified", bool(mfa_verified))
        setattr(user, "_jwt_support_grant", support_grant)
        setattr(user, "_jwt_platform", platform)
        try:
            refresh = cls.get_token(user)
            access = refresh.access_token
            if support_grant is not None:
                support_grant.mark_used()
            return refresh, access
        finally:
            if hasattr(user, "_jwt_active_profile"):
                delattr(user, "_jwt_active_profile")
            if hasattr(user, "_jwt_mfa_verified"):
                delattr(user, "_jwt_mfa_verified")
            if hasattr(user, "_jwt_support_grant"):
                delattr(user, "_jwt_support_grant")
            if hasattr(user, "_jwt_platform"):
                delattr(user, "_jwt_platform")

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        profile = getattr(user, "_jwt_active_profile", None)
        support_grant = getattr(user, "_jwt_support_grant", None)
        platform = getattr(user, "_jwt_platform", None) or PlatformChoices.INTERA_IMS
        if profile is None and user.profile_id:
            access = cls.resolve_active_profile_access(user, profile_id=user.profile_id)
            profile = access.profile
            support_grant = access.support_grant
        cls._apply_claims(token, user, profile, support_grant=support_grant, platform=platform)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        access = self.resolve_active_profile_access(
            user,
            profile_id=attrs.get("profile_id"),
            company_code=(attrs.get("company_code") or "").strip() or None,
            support_access_grant_id=attrs.get("support_access_grant_id"),
        )
        profile = access.profile
        if profile and user.profile_id != profile.id:
            User.objects.filter(id=user.id).update(profile=profile)
            user.profile = profile

        refresh, access_token = self.issue_tokens_for_profile(
            user,
            profile,
            mfa_verified=False,
            support_grant=access.support_grant,
            platform=attrs.get("platform", PlatformChoices.INTERA_IMS),
        )
        if access.support_grant is not None:
            publish_support_access_workspace_entered(
                access.support_grant,
                actor=build_actor(
                    request=self.context.get("request"),
                    user=user,
                    role=access.support_grant.membership_role,
                ),
            )
        data["refresh"] = str(refresh)
        data["access"] = str(access_token)
        data["authorization_context"] = issue_authorization_context(
            user,
            profile=profile,
            support_grant=access.support_grant,
            platform=attrs.get("platform", PlatformChoices.INTERA_IMS),
        )

        accessible_profiles = self.list_accessible_profile_contexts(user)
        data.update({
            "id": user.id,
            "username": user.username,
            "is_verified": getattr(user, "is_verified", False),
            "is_staff": bool(user.is_staff),
            "is_superuser": bool(user.is_superuser),
            "profile": str(profile.id) if profile else None,
            "profile_context": self._profile_payload(profile, user, support_grant=access.support_grant),
            "profiles": [
                self._profile_payload(item.profile, user, support_grant=item.support_grant)
                for item in accessible_profiles
            ],
            "currency": profile.currency if profile else None,
            "email": user.email,
            "first_name": getattr(user, "first_name", ""),
        })
        return data



class SocialJWTSerializer(ProviderAuthSerializer):
    """
    Override Djoser social provider serializer to mint our JWTs (with custom claims).
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        user = data.get("user") or getattr(self, "user", None) or self.context.get("request").user
        if not user or not user.is_authenticated:
            raise DjangoValidationError("Unable to resolve authenticated user for social login.")
        # keep only the user; create() will build tokens
        return {"user": user}

    def create(self, validated_data):
        user = validated_data["user"]
        profile_access = MyTokenObtainPairSerializer.resolve_active_profile_access(user)
        refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            user,
            profile_access.profile,
            support_grant=profile_access.support_grant,
        )
        return {
            "user": user,
            "refresh": str(refresh),
            "access": str(access),
            "authorization_context": issue_authorization_context(
                user,
                profile=profile_access.profile,
                support_grant=profile_access.support_grant,
            ),
            "id": user.id,
            "username": user.username,
            "is_verified": getattr(user, "is_verified", False),
            "is_staff": bool(user.is_staff),
            "is_superuser": bool(user.is_superuser),
            "profile": str(profile_access.profile.id) if profile_access.profile else None,
            "profile_context": self._profile_payload(
                profile_access.profile,
                user,
                support_grant=profile_access.support_grant,
            ),
            "profiles": [
                self._profile_payload(
                    item.profile,
                    user,
                    support_grant=item.support_grant,
                )
                for item in self.list_accessible_profile_contexts(user)
            ],
            "currency": profile_access.profile.currency if profile_access.profile else None,
            "email": user.email,
            "first_name": getattr(user, "first_name", ""),
        }


class TokenRefreshSerializer(BaseTokenRefreshSerializer):
    """Attach custom claims to refreshed access tokens."""

    def validate(self, attrs):
        data = super().validate(attrs)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        raw_refresh = data.get("refresh") or attrs.get("refresh")

        if (not user or not user.is_authenticated) and raw_refresh:
            try:
                refresh_token = RefreshToken(raw_refresh)
                user_id = refresh_token.get("user_id")
                if user_id:
                    user = User.objects.filter(id=user_id).first()
            except Exception:
                user = None

        if not user or not user.is_authenticated:
            return data

        active_access = None
        mfa_verified_claim = False
        platform = PlatformChoices.INTERA_IMS
        if raw_refresh:
            try:
                refresh_payload = RefreshToken(raw_refresh)
                mfa_verified_claim = bool(refresh_payload.get("mfa_verified"))
                profile_id = refresh_payload.get("profile_id")
                platform = refresh_payload.get("platform", PlatformChoices.INTERA_IMS)
                support_access_grant_id = refresh_payload.get("support_access_grant_id")
                if support_access_grant_id:
                    active_access = MyTokenObtainPairSerializer.resolve_active_profile_access(
                        user,
                        profile_id=profile_id if profile_id else None,
                        support_access_grant_id=support_access_grant_id,
                    )
                    if not active_access.profile or not active_access.support_grant:
                        raise serializers.ValidationError(
                            {"detail": "Support access grant is no longer active for this workspace."}
                        )
                elif profile_id:
                    active_access = MyTokenObtainPairSerializer.resolve_active_profile_access(
                        user,
                        profile_id=profile_id,
                    )
            except serializers.ValidationError:
                raise
            except Exception:
                active_access = None
                mfa_verified_claim = False

        if not active_access:
            active_access = MyTokenObtainPairSerializer.resolve_active_profile_access(user)

        mfa_verified = bool(active_access.profile and mfa_verified_claim)
        custom_refresh, custom_access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            user,
            active_access.profile,
            mfa_verified=mfa_verified,
            support_grant=active_access.support_grant,
            platform=platform,
        )
        data["access"] = str(custom_access)
        data["authorization_context"] = issue_authorization_context(
            user,
            profile=active_access.profile,
            support_grant=active_access.support_grant,
            platform=platform,
        )
        if "refresh" in data:
            data["refresh"] = str(custom_refresh)

        profile = active_access.profile
        data.update({
            'id': user.id,
            'username': user.username,
            'is_verified': getattr(user, 'is_verified', False),
            'is_staff': bool(user.is_staff),
            'is_superuser': bool(user.is_superuser),
            'profile': str(profile.id) if profile else None,
            'profile_context': MyTokenObtainPairSerializer._profile_payload(
                profile,
                user,
                support_grant=active_access.support_grant,
            ),
            'profiles': [
                MyTokenObtainPairSerializer._profile_payload(
                    item.profile,
                    user,
                    support_grant=item.support_grant,
                )
                for item in MyTokenObtainPairSerializer.list_accessible_profile_contexts(user)
            ],
            'currency': profile.currency if profile else None,
            'email': user.email,
            'first_name': getattr(user, 'first_name', ''),
        })
        return data




class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name','role']
        ref_name = "AccountsUser"

class VerificationCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationCode
        fields = ['id', 'user', 'code', 'verification_type', 'expires_at', 'created_at']
        read_only_fields = ['code', 'expires_at', 'created_at']



class UserCreateSerializer(BaseUserCreateSerializer):
    terms_accepted = serializers.BooleanField(write_only=True, required=True)
    privacy_accepted = serializers.BooleanField(write_only=True, required=True)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'password',
            'terms_accepted', 'privacy_accepted', 'referral_code',
        )

    def validate(self, attrs):
        # Remove consent-only fields before Djoser builds a User instance.
        attrs = validate_signup_consents(attrs)
        return _resolve_referrer(super().validate(attrs))
        
    def create(self, validated_data):
        referrer = validated_data.pop('referrer_user', None)
        validated_data.pop('referral_code', None)
        user = User.objects.create_user(
            email=validated_data['email'].lower(),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            referred_by=referrer,
        )
        record_signup_consents(user, request=self.context.get("request"), source="djoser_signup")
        return user






class MyUserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    picture = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'get_full_name',
            'role',
            'phone',
            'sex',
            'date_of_birth',
            'picture',
            'is_verified',
            'mfa_enabled',
            'has_setup_mfa',
            'profile',
            'referral_code',
        )
        read_only_fields = (
            'id', 'get_full_name',
        )
        ref_name = "AccountsCoreMyUser"

    def get_picture(self, obj):
        return obj.get_picture()

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""
    
    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'phone',
            'sex',
            'date_of_birth',
            'picture',
        )


class OwnerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    re_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    terms_accepted = serializers.BooleanField(write_only=True, required=True)
    privacy_accepted = serializers.BooleanField(write_only=True, required=True)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = validate_signup_consents(attrs)
        if attrs["password"] != attrs["re_password"]:
            raise serializers.ValidationError({"re_password": "Passwords do not match"})
        validate_password(attrs["password"])
        if User.objects.filter(email=attrs["email"].lower()).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        return _resolve_referrer(attrs)

    def create(self, validated_data):
        validated_data.pop("re_password")
        referrer = validated_data.pop('referrer_user', None)
        validated_data.pop('referral_code', None)
        user = User.objects.create_user(
            email=validated_data["email"].lower(),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            referred_by=referrer,
        )
        record_signup_consents(user, request=self.context.get("request"), source="owner_signup")
        return user


class TenantManagedUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        attrs["email"] = email
        existing_user = User.objects.filter(email=email).first()
        attrs["existing_user"] = existing_user

        password = attrs.get("password")
        if existing_user:
            return attrs
        if not password:
            raise serializers.ValidationError({"password": "Password is required for new users."})
        validate_password(password)
        return attrs

    def create(self, validated_data):
        profile = self.context["profile"]
        existing_user = validated_data.pop("existing_user", None)
        email = validated_data["email"]

        if existing_user:
            user = existing_user
        else:
            user = User.objects.create_user(
                email=email,
                password=validated_data.get("password"),
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                phone=validated_data.get("phone"),
                profile=profile,
            )

        CompanyMembership.objects.update_or_create(
            user=user,
            profile=profile,
            defaults={
                "role": CompanyMembership.MembershipRole.MEMBER,
                "is_active": True,
            },
        )
        if not user.profile_id:
            user.profile = profile
            user.save(update_fields=["profile"])

        return user

class CompanyContextSwitchSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField(required=False)
    company_code = serializers.CharField(required=False, allow_blank=True)
    support_access_grant_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        profile_id = attrs.get("profile_id")
        company_code = (attrs.get("company_code") or "").strip()
        if not profile_id and not company_code:
            raise serializers.ValidationError("Either profile_id or company_code must be provided.")
        attrs["company_code"] = company_code or None
        return attrs



class PlanMetadataSerializer(serializers.Serializer):
    """Lightweight summary of a plan stored inside user metadata."""

    id = serializers.CharField(required=False, allow_blank=True)
    slug = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            instance = {}
        return super().to_representation(instance)


class PlanFeatureQuotaSerializer(serializers.Serializer):
    """Serializer for a single feature quota entry."""

    limit_type = serializers.CharField(required=False, allow_blank=True)
    limit_value = serializers.IntegerField(required=False, allow_null=True, default=0)
    service_area = serializers.CharField(required=False, allow_blank=True)
    service_identifier = serializers.CharField(required=False, allow_blank=True)

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            instance = {}
        data = super().to_representation(instance)
        if data.get('limit_value') is None:
            data['limit_value'] = 0
        return data


class UserQuotaMetadataSerializer(serializers.Serializer):
    """Serializer for the subscription metadata embedded on the user."""

    plan = PlanMetadataSerializer(required=False, allow_null=True)
    plan_features = serializers.SerializerMethodField()

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            instance = {}
        return super().to_representation(instance)

    def get_plan_features(self, instance):
        if not isinstance(instance, dict):
            return {}
        features = instance.get('plan_features') or {}
        if not isinstance(features, dict):
            return {}
        sanitized = {}
        for feature_key, feature_data in features.items():
            if not isinstance(feature_data, dict):
                continue
            serializer = PlanFeatureQuotaSerializer(instance=feature_data)
            sanitized[feature_key] = serializer.data
        return sanitized
