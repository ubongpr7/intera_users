from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from cities_light.models import City, Country, Region, SubRegion

from mainapps.accounts.api.serializers import MyUserSerializer
from mainapps.permit.models import CustomUserPermission, PlatformChoices
from mainapps.profile.support_access import user_has_direct_profile_access
from .support_access_presets import (
    DISALLOWED_SUPPORT_CUSTOM_PERMISSION_CODENAMES,
    get_support_access_preset,
    get_support_access_presets,
)
from .models import (
    CompanyInvitation,
    CompanyMembership,
    CompanyProfile, CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment,
     RecallPolicy, ReorderStrategy, InventoryPolicy, SupportAccessGrant,
    TrustedWorkspaceDevice,
)

User = get_user_model()

class CompanyProfileAddressSerializer(serializers.ModelSerializer):
    """Serializer for addresses"""
    country_name = serializers.SerializerMethodField()
    region_name = serializers.SerializerMethodField()
    subregion_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    address_id = serializers.UUIDField(source='shared_address_id', read_only=True)
    
    class Meta:
        model = CompanyProfileAddress
        fields = '__all__'
        extra_fields = ['address_id']
        read_only_fields = ['profile']

    @staticmethod
    def _resolve_geo_name(model_class, raw_value):
        if raw_value in (None, ""):
            return None
        try:
            return model_class.objects.only("name").get(id=int(raw_value)).name
        except (TypeError, ValueError, model_class.DoesNotExist):
            return raw_value

    def get_country_name(self, obj):
        return self._resolve_geo_name(Country, obj.country)

    def get_region_name(self, obj):
        return self._resolve_geo_name(Region, obj.region)

    def get_subregion_name(self, obj):
        return self._resolve_geo_name(SubRegion, obj.subregion)

    def get_city_name(self, obj):
        return self._resolve_geo_name(City, obj.city)

class CompanyProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for company profile lists"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    staff_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyProfile
        fields = [
            'id', 'name', 'industry', 'employees_count', 'is_verified',
            'owner_name', 'staff_count', 'created_at'
        ]
    
    def get_staff_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

class CompanyProfileDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for company profiles"""
    owner = MyUserSerializer(read_only=True)
    headquarters_address = CompanyProfileAddressSerializer(read_only=True)
    staff_count = serializers.SerializerMethodField()
    roles_count = serializers.SerializerMethodField()
    groups_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyProfile
        fields = '__all__'
        read_only_fields = ['owner', 'is_verified', 'verification_date']
    
    def get_staff_count(self, obj):
        return obj.memberships.filter(is_active=True).count()
    
    def get_roles_count(self, obj):
        return obj.get_staff_roles().count()
    
    def get_groups_count(self, obj):
        return obj.get_staff_groups().count()

class StaffRoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for staff role lists"""
    assignments_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffRole
        fields = ['id', 'name', 'platform', 'description', 'is_system', 'assignments_count', 'created_at', 'permission_count']
    
    def get_assignments_count(self, obj):
        return obj.assignments.count() or 0
    
    def get_permission_count(self,obj):
        return obj.permissions.count()

class StaffRoleSerializer(serializers.ModelSerializer):
    """Detailed serializer for staff roles"""
    created_by = MyUserSerializer(read_only=True)
    assignments_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    
    
    class Meta:
        model = StaffRole
        fields = '__all__'
        read_only_fields = ['profile', 'created_by', 'is_system']
    
    def get_assignments_count(self, obj):
        return obj.assignments.count()
    def get_permission_count(self,obj):
        return obj.permissions.count()

class StaffGroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for staff group lists"""
    users_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    
    
    class Meta:
        model = StaffGroup
        fields = ['id', 'name', 'platform', 'description', 'is_system', 'users_count', 'created_at', 'permission_count']
    
    def get_users_count(self, obj):
        return obj.users.count()
    def get_permission_count(self,obj):
        return obj.permissions.count()
class StaffGroupSerializer(serializers.ModelSerializer):
    """Detailed serializer for staff groups"""
    created_by = MyUserSerializer(read_only=True)
    users_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()

    
    
    class Meta:
        model = StaffGroup
        fields = '__all__'
        read_only_fields = ['profile', 'created_by', 'is_system']
    
    def get_users_count(self, obj):
        return obj.users.count()

    def get_permission_count(self,obj):
        return obj.permissions.count()
class StaffAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for staff role assignments"""
    user = MyUserSerializer(read_only=True)
    role = StaffRoleListSerializer(read_only=True)
    assigned_by = MyUserSerializer(read_only=True)
    is_currently_active = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffRoleAssignment
        fields = '__all__'
        read_only_fields = ['profile', 'assigned_by']
    
    def get_is_currently_active(self, obj):
        now = timezone.now()
        return (
            obj.is_active and
            obj.start_date <= now and
            (obj.end_date is None or obj.end_date >= now)
        )


class CompanyMembershipStaffSerializer(serializers.ModelSerializer):
    user = MyUserSerializer(read_only=True)
    membership_role = serializers.CharField(source="role", read_only=True)

    class Meta:
        model = CompanyMembership
        fields = [
            "id",
            "user",
            "profile",
            "membership_role",
            "is_active",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = fields


class TrustedWorkspaceDeviceSerializer(serializers.ModelSerializer):
    """Explicit contract for durable workspace device trust and local proof."""

    status = serializers.SerializerMethodField()
    signed_enrollment_proof = serializers.SerializerMethodField()
    capabilities = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
    )
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        default=PlatformChoices.HOSPERATOR,
    )

    class Meta:
        model = TrustedWorkspaceDevice
        fields = [
            "id",
            "profile",
            "platform",
            "device_identifier",
            "device_label",
            "capabilities",
            "is_active",
            "is_revoked",
            "status",
            "created_by",
            "revoked_by",
            "revoked_at",
            "last_seen_at",
            "created_at",
            "updated_at",
            "signed_enrollment_proof",
        ]
        read_only_fields = [
            "id",
            "profile",
            "is_active",
            "is_revoked",
            "status",
            "created_by",
            "revoked_by",
            "revoked_at",
            "last_seen_at",
            "created_at",
            "updated_at",
            "signed_enrollment_proof",
        ]

    def validate_device_identifier(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A device identifier is required.")
        if any(ord(character) < 32 for character in value):
            raise serializers.ValidationError("Device identifier contains an invalid control character.")
        return value

    def validate_capabilities(self, value):
        normalized = sorted({item.strip() for item in value if item.strip()})
        if len(normalized) > 16:
            raise serializers.ValidationError("A device may have at most 16 capabilities.")
        return normalized

    def get_status(self, obj):
        return obj.status

    def get_signed_enrollment_proof(self, obj):
        request = self.context.get("request")
        current_device_id = str(request.headers.get("X-Device-ID", "")).strip() if request else ""
        if not obj.is_active or obj.is_revoked or current_device_id != obj.device_identifier:
            return None
        from mainapps.accounts.authorization_context import issue_device_enrollment_proof

        return issue_device_enrollment_proof(obj, user_id=getattr(request.user, "id", None))

class AddStaffSerializer(serializers.Serializer):
    """Serializer for adding staff to profile"""
    user_id = serializers.CharField()
    role_id = serializers.CharField()
    start_date = serializers.DateTimeField(default=timezone.now)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate(self, data):
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError("End date cannot be before start date")
        return data

class AssignUserToRoleSerializer(serializers.Serializer):
    """Serializer for assigning user to role"""
    user_id = serializers.CharField()
    start_date = serializers.DateTimeField(default=timezone.now)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate(self, data):
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] < data['start_date']:
                raise serializers.ValidationError("End date cannot be before start date")
        return data


class RecallPolicySerializer(serializers.ModelSerializer):
    """Serializer for recall policies"""
    class Meta:
        model = RecallPolicy
        fields = '__all__'

class ReorderStrategySerializer(serializers.ModelSerializer):
    """Serializer for reorder strategies"""
    class Meta:
        model = ReorderStrategy
        fields = '__all__'

class InventoryPolicySerializer(serializers.ModelSerializer):
    """Serializer for inventory policies"""
    class Meta:
        model = InventoryPolicy
        fields = '__all__'

 
class StaffRoleAssignmentSerializer(serializers.ModelSerializer):
    role_name=serializers.CharField(source='role.name',read_only=True)
    assigned_by_email = serializers.CharField(source="assigned_by.email", read_only=True)
    class Meta:
        model = StaffRoleAssignment
        fields = [
            'id',
            'user',
            'profile',
            'role',
            'role_name',
            'is_active',
            'start_date',
            'end_date',
            'assigned_by',
            'assigned_by_email',
            'assigned_at',
        ]
        read_only_fields = ['id', 'profile', 'assigned_by', 'assigned_by_email', 'assigned_at']


class CompanyInvitationSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    invited_by_email = serializers.CharField(source="invited_by.email", read_only=True)
    accepted_by_email = serializers.CharField(source="accepted_by.email", read_only=True)

    class Meta:
        model = CompanyInvitation
        fields = "__all__"
        read_only_fields = [
            "id",
            "invitation_code",
            "status",
            "responded_at",
            "accepted_by",
            "created_at",
            "updated_at",
            "profile",
            "invited_by",
        ]
        extra_kwargs = {
            "expires_at": {"required": False, "allow_null": True},
        }


class CompanyInvitationRespondSerializer(serializers.Serializer):
    invitation_code = serializers.CharField()


class SupportAccessPresetSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class SupportAccessGrantSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    grantee_user = MyUserSerializer(read_only=True)
    accepted_by = MyUserSerializer(read_only=True)
    created_by = MyUserSerializer(read_only=True)
    approved_by = MyUserSerializer(read_only=True)
    revoked_by = MyUserSerializer(read_only=True)
    custom_permissions = serializers.SlugRelatedField(
        slug_field="codename",
        many=True,
        read_only=True,
    )
    status = serializers.SerializerMethodField()
    effective_permissions = serializers.SerializerMethodField()
    preset = serializers.SerializerMethodField()

    class Meta:
        model = SupportAccessGrant
        fields = [
            "id",
            "profile",
            "profile_name",
            "grantee_user",
            "accepted_by",
            "grantee_email_snapshot",
            "invitation_code",
            "created_by",
            "approved_by",
            "revoked_by",
            "reason",
            "ticket_reference",
            "permission_mode",
            "membership_role",
            "custom_permissions",
            "effective_permissions",
            "starts_at",
            "expires_at",
            "revoked_at",
            "responded_at",
            "last_used_at",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "preset",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return obj.current_status

    def get_effective_permissions(self, obj):
        return obj.effective_permission_codenames()

    def get_preset(self, obj):
        preset = get_support_access_preset(obj.permission_mode)
        if not preset:
            return None
        return SupportAccessPresetSerializer(instance=preset).data


class SupportAccessGrantCreateSerializer(serializers.ModelSerializer):
    grantee_email = serializers.EmailField(write_only=True)
    custom_permissions = serializers.SlugRelatedField(
        slug_field="codename",
        many=True,
        queryset=CustomUserPermission.objects.all(),
        required=False,
    )
    starts_at = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = SupportAccessGrant
        fields = [
            "id",
            "grantee_email",
            "reason",
            "ticket_reference",
            "permission_mode",
            "membership_role",
            "custom_permissions",
            "starts_at",
            "expires_at",
            "notes",
        ]
        read_only_fields = ["id"]

    def validate_permission_mode(self, value):
        if not get_support_access_preset(value):
            raise serializers.ValidationError("Unsupported support access preset.")
        return value

    def validate_membership_role(self, value):
        if value == CompanyMembership.MembershipRole.OWNER:
            raise serializers.ValidationError("Support access cannot assign the owner role.")
        return value

    def validate_custom_permissions(self, permissions):
        disallowed = sorted(
            permission.codename
            for permission in permissions
            if permission.codename in DISALLOWED_SUPPORT_CUSTOM_PERMISSION_CODENAMES
        )
        if disallowed:
            raise serializers.ValidationError(
                f"These permissions cannot be granted through temporary support access: {', '.join(disallowed)}."
            )
        return permissions

    def validate(self, attrs):
        profile = self.context["profile"]
        grantee_email = attrs["grantee_email"].strip().lower()
        grantee_user = User.objects.filter(email__iexact=grantee_email, is_active=True).first()
        starts_at = attrs.get("starts_at") or timezone.now()
        expires_at = attrs["expires_at"]

        if expires_at <= starts_at:
            raise serializers.ValidationError({"expires_at": "Expiry must be after the start time."})
        if expires_at <= timezone.now():
            raise serializers.ValidationError({"expires_at": "Expiry must be in the future."})
        if grantee_user and user_has_direct_profile_access(grantee_user, profile):
            raise serializers.ValidationError(
                {"grantee_email": "This user already has direct access to the requested workspace."}
            )
        if SupportAccessGrant.objects.filter(
            profile=profile,
            revoked_at__isnull=True,
            grantee_email_snapshot__iexact=grantee_email,
            starts_at__lt=expires_at,
            expires_at__gt=starts_at,
        ).exclude(status__in=[SupportAccessGrant.Status.CONSUMED, SupportAccessGrant.Status.DECLINED]).exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["An overlapping support access request already exists for this email and workspace."]}
            )

        attrs["grantee_email"] = grantee_email
        attrs["grantee_user"] = grantee_user
        attrs["starts_at"] = starts_at
        return attrs

    def create(self, validated_data):
        grantee_email = validated_data.pop("grantee_email")
        custom_permissions = validated_data.pop("custom_permissions", [])
        request = self.context["request"]
        profile = self.context["profile"]
        grant = SupportAccessGrant.objects.create(
            profile=profile,
            created_by=request.user,
            approved_by=request.user,
            grantee_email_snapshot=grantee_email,
            **validated_data,
        )
        if custom_permissions:
            grant.custom_permissions.set(custom_permissions)
        return grant


class SupportAccessGrantExtendSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        grant = self.context["grant"]
        expires_at = attrs["expires_at"]

        if grant.current_status == SupportAccessGrant.Status.REVOKED:
            raise serializers.ValidationError({"detail": "Revoked support grants cannot be extended."})
        if expires_at <= timezone.now():
            raise serializers.ValidationError({"expires_at": "Expiry must be in the future."})
        if expires_at <= grant.expires_at:
            raise serializers.ValidationError({"expires_at": "New expiry must be later than the current expiry."})
        if SupportAccessGrant.objects.filter(
            profile=grant.profile,
            revoked_at__isnull=True,
            grantee_email_snapshot__iexact=grant.grantee_email_snapshot,
            starts_at__lt=expires_at,
            expires_at__gt=grant.starts_at,
        ).exclude(id=grant.id).exclude(
            status__in=[SupportAccessGrant.Status.CONSUMED, SupportAccessGrant.Status.DECLINED]
        ).exists():
            raise serializers.ValidationError(
                {"expires_at": "The requested extension overlaps another support access request for this email."}
            )
        return attrs


class SupportAccessGrantRevokeSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class SupportAccessGrantRespondSerializer(serializers.Serializer):
    invitation_code = serializers.CharField()


def serialize_support_access_presets():
    return SupportAccessPresetSerializer(instance=get_support_access_presets(), many=True).data
