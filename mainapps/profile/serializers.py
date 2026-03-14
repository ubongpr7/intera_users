from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

from mainapps.accounts.api.serializers import MyUserSerializer
from .models import (
    CompanyInvitation,
    CompanyProfile, CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment,
     RecallPolicy, ReorderStrategy, InventoryPolicy, ProfileAgent, ModelVersion
)

User = get_user_model()

class CompanyProfileAddressSerializer(serializers.ModelSerializer):
    """Serializer for addresses"""
    country_name = serializers.CharField(source='country', read_only=True)
    region_name = serializers.CharField(source='region', read_only=True)
    subregion_name = serializers.CharField(source='subregion', read_only=True)
    city_name = serializers.CharField(source='city', read_only=True)
    
    class Meta:
        model = CompanyProfileAddress
        fields = '__all__'
        read_only_fields = ['profile']

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
        return obj.staff_groups().count()   

class StaffRoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for staff role lists"""
    assignments_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffRole
        fields = ['id', 'name', 'description',  'assignments_count', 'created_at','permission_count']
    
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
        read_only_fields = ['profile', 'created_by']
    
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
        fields = ['id', 'name', 'description',  'users_count', 'created_at','permission_count']
    
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
        read_only_fields = ['profile', 'created_by']
    
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
    class Meta:
        model = StaffRoleAssignment
        fields = ['id','role_name','is_active','role','start_date','end_date']
        read_only_fields = ['id']


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


def _mask_secret(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}{'*' * (len(raw) - 8)}{raw[-4:]}"


class ModelVersionOptionSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="llm.provider", read_only=True)
    provider_label = serializers.CharField(source="llm.get_provider_display", read_only=True)
    base_url = serializers.CharField(source="llm.base_url", read_only=True, allow_null=True)

    class Meta:
        model = ModelVersion
        fields = ["id", "provider", "provider_label", "model_name", "base_url"]


class ProfileAgentSetupSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="version.llm.provider", read_only=True)
    provider_label = serializers.CharField(source="version.llm.get_provider_display", read_only=True)
    model_name = serializers.CharField(source="version.model_name", read_only=True)
    provider_base_url = serializers.CharField(source="version.llm.base_url", read_only=True, allow_null=True)
    effective_base_url = serializers.SerializerMethodField()
    version = serializers.PrimaryKeyRelatedField(queryset=ModelVersion.objects.select_related("llm").all())
    has_api_key = serializers.SerializerMethodField()
    has_tavily_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    tavily_api_key_masked = serializers.SerializerMethodField()
    base_url = serializers.CharField(required=False, allow_blank=True, allow_null=True, trim_whitespace=True)
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=True)
    tavily_api_key = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = ProfileAgent
        fields = [
            "id",
            "profile",
            "name",
            "version",
            "provider",
            "provider_label",
            "model_name",
            "provider_base_url",
            "effective_base_url",
            "base_url",
            "special_instruction",
            "system_instruction",
            "assistant_instruction",
            "api_key",
            "tavily_api_key",
            "has_api_key",
            "has_tavily_api_key",
            "api_key_masked",
            "tavily_api_key_masked",
        ]
        read_only_fields = [
            "id",
            "profile",
            "provider",
            "provider_label",
            "model_name",
            "provider_base_url",
            "effective_base_url",
            "has_api_key",
            "has_tavily_api_key",
            "api_key_masked",
            "tavily_api_key_masked",
        ]

    def validate(self, attrs):
        if self.instance is None:
            missing_fields = []
            for field_name in ("name", "version", "api_key", "tavily_api_key"):
                if not attrs.get(field_name):
                    missing_fields.append(field_name)
            if missing_fields:
                raise serializers.ValidationError(
                    {field: "This field is required when creating agent setup." for field in missing_fields}
                )
        return attrs

    def get_has_api_key(self, obj):
        return bool(obj.decrypted_api_key)

    def get_effective_base_url(self, obj):
        return obj.effective_base_url or None

    def get_has_tavily_api_key(self, obj):
        return bool(obj.decrypted_tavily_api_key)

    def get_api_key_masked(self, obj):
        return _mask_secret(obj.decrypted_api_key)

    def get_tavily_api_key_masked(self, obj):
        return _mask_secret(obj.decrypted_tavily_api_key)
        
    
