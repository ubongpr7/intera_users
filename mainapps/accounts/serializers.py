from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import User, VerificationCode
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as BaseTokenRefreshSerializer

from djoser.social.serializers import ProviderAuthSerializer
from mainapps.profile.models import CompanyMembership, CompanyProfile


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    profile_id = serializers.UUIDField(required=False, write_only=True)
    company_code = serializers.CharField(required=False, write_only=True, allow_blank=True)

    @classmethod
    def _active_memberships(cls, user):
        return CompanyMembership.objects.filter(user=user, is_active=True).select_related("profile")

    @classmethod
    def _owned_profiles(cls, user):
        return CompanyProfile.objects.filter(owner=user)

    @classmethod
    def user_has_profile_access(cls, user, profile):
        if not profile:
            return False
        if profile.owner_id == user.id:
            return True
        return CompanyMembership.objects.filter(
            user=user,
            profile=profile,
            is_active=True,
        ).exists()

    @classmethod
    def list_accessible_profiles(cls, user):
        profiles_by_id = {}
        for owned in cls._owned_profiles(user):
            profiles_by_id[str(owned.id)] = owned
        for membership in cls._active_memberships(user):
            profiles_by_id[str(membership.profile_id)] = membership.profile
        return list(profiles_by_id.values())

    @classmethod
    def resolve_active_profile(cls, user, profile_id=None, company_code=None):
        requested_profile = None
        if profile_id:
            requested_profile = CompanyProfile.objects.filter(id=profile_id).first()
            if not requested_profile:
                raise serializers.ValidationError({"profile_id": "Company profile not found."})
        elif company_code:
            requested_profile = CompanyProfile.objects.filter(company_code__iexact=company_code).first()
            if not requested_profile:
                raise serializers.ValidationError({"company_code": "Invalid company code."})

        if requested_profile:
            if not cls.user_has_profile_access(user, requested_profile):
                raise serializers.ValidationError(
                    {"profile_id": "You do not have access to the requested company profile."}
                )
            return requested_profile

        if user.profile_id:
            current_profile = CompanyProfile.objects.filter(id=user.profile_id).first()
            if current_profile and cls.user_has_profile_access(user, current_profile):
                return current_profile

        profiles = cls.list_accessible_profiles(user)
        if len(profiles) == 1:
            return profiles[0]
        return None

    @classmethod
    def get_all_permissions(cls, user, profile=None):
        user_perms = set()
        user_perms.update(user.custom_permissions.all().values_list("codename", flat=True))
        if not profile:
            return sorted(user_perms)

        current_time = timezone.now()
        try:
            for assignment in user.roles.filter(profile=profile, is_active=True).select_related("role"):
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
            groups = user.staff_groups.filter(profile=profile, is_active=True)
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
            user_perms.update(membership.custom_permissions.values_list("codename", flat=True))

        return sorted(user_perms)

    @classmethod
    def _profile_payload(cls, profile, user):
        if not profile:
            return None
        if profile.owner_id == user.id:
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
            "owner_id": str(profile.owner_id) if profile.owner_id else None,
            "currency": profile.currency,
            "role": role,
            "membership_id": membership_id,
        }

    @classmethod
    def _apply_claims(cls, token, user, profile):
        token["permissions"] = cls.get_all_permissions(user, profile=profile)
        token["profile_id"] = str(profile.id) if profile else None
        token["company_code"] = profile.company_code if profile else None
        token["email"] = user.email
        token["mfa_enabled"] = bool(getattr(user, "mfa_enabled", False))
        token["has_setup_mfa"] = bool(getattr(user, "has_setup_mfa", False))
        token["owner_id"] = str(profile.owner_id) if profile and profile.owner_id else None

        role = None
        if profile:
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

        token["mfa_verified"] = bool(getattr(user, "_jwt_mfa_verified", False))

    @classmethod
    def issue_tokens_for_profile(cls, user, profile, mfa_verified=False):
        setattr(user, "_jwt_active_profile", profile)
        setattr(user, "_jwt_mfa_verified", bool(mfa_verified))
        try:
            refresh = cls.get_token(user)
            access = refresh.access_token
            return refresh, access
        finally:
            if hasattr(user, "_jwt_active_profile"):
                delattr(user, "_jwt_active_profile")
            if hasattr(user, "_jwt_mfa_verified"):
                delattr(user, "_jwt_mfa_verified")

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        profile = getattr(user, "_jwt_active_profile", None)
        if profile is None and user.profile_id:
            profile = CompanyProfile.objects.filter(id=user.profile_id).first()
        cls._apply_claims(token, user, profile)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        profile = self.resolve_active_profile(
            user,
            profile_id=attrs.get("profile_id"),
            company_code=(attrs.get("company_code") or "").strip() or None,
        )
        if profile and user.profile_id != profile.id:
            User.objects.filter(id=user.id).update(profile=profile)
            user.profile = profile

        refresh, access = self.issue_tokens_for_profile(user, profile, mfa_verified=False)
        data["refresh"] = str(refresh)
        data["access"] = str(access)

        accessible_profiles = self.list_accessible_profiles(user)
        data.update({
            "id": user.id,
            "username": user.username,
            "is_verified": getattr(user, "is_verified", False),
            "profile": str(profile.id) if profile else None,
            "profile_context": self._profile_payload(profile, user),
            "profiles": [self._profile_payload(item, user) for item in accessible_profiles],
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
        profile = MyTokenObtainPairSerializer.resolve_active_profile(user)
        refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(user, profile)
        return {
            "user": user,
            "refresh": str(refresh),
            "access": str(access),
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

        active_profile = None
        mfa_verified_claim = False
        if raw_refresh:
            try:
                refresh_payload = RefreshToken(raw_refresh)
                mfa_verified_claim = bool(refresh_payload.get("mfa_verified"))
                profile_id = refresh_payload.get("profile_id")
                if profile_id:
                    active_profile = CompanyProfile.objects.filter(id=profile_id).first()
                    if active_profile and not MyTokenObtainPairSerializer.user_has_profile_access(user, active_profile):
                        active_profile = None
            except Exception:
                active_profile = None
                mfa_verified_claim = False

        if not active_profile:
            active_profile = MyTokenObtainPairSerializer.resolve_active_profile(user)

        mfa_verified = bool(active_profile and mfa_verified_claim)
        custom_refresh, custom_access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            user,
            active_profile,
            mfa_verified=mfa_verified,
        )
        data["access"] = str(custom_access)
        if "refresh" in data:
            data["refresh"] = str(custom_refresh)

        profile = active_profile
        data.update({
            'id': user.id,
            'username': user.username,
            'is_verified': getattr(user, 'is_verified', False),
            'profile': str(profile.id) if profile else None,
            'profile_context': MyTokenObtainPairSerializer._profile_payload(profile, user),
            'profiles': [
                MyTokenObtainPairSerializer._profile_payload(item, user)
                for item in MyTokenObtainPairSerializer.list_accessible_profiles(user)
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
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'password')
        
    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'].lower(),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )






class MyUserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'get_full_name','role'
        )
        read_only_fields = (
            'id', 'get_full_name',
        )

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""
    
    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 
        )


class OwnerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    re_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["re_password"]:
            raise serializers.ValidationError({"re_password": "Passwords do not match"})
        validate_password(attrs["password"])
        if User.objects.filter(email=attrs["email"].lower()).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("re_password")
        user = User.objects.create_user(
            email=validated_data["email"].lower(),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
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
    profile_id = serializers.UUIDField(required=False)
    company_code = serializers.CharField(required=False, allow_blank=True)

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
