from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

from mainapps.accounts.api.serializers import MyUserSerializer
from .models import (
    CompanyProfile, CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment,
    ActivityLog, RecallPolicy, ReorderStrategy, InventoryPolicy
)

User = get_user_model()

class CompanyProfileAddressSerializer(serializers.ModelSerializer):
    """Serializer for addresses"""
    country_name = serializers.CharField(source='country.name', read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    subregion_name = serializers.CharField(source='subregion.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    
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
        return obj.staff.count()

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
        return obj.staff.count()
    
    def get_roles_count(self, obj):
        return obj.get_staff_roles().count()
    
    def get_groups_count(self, obj):
        return obj.staff_groups().count()   

class StaffRoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for staff role lists"""
    assignments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffRole
        fields = ['id', 'name', 'description',  'assignments_count', 'created_at']
    
    def get_assignments_count(self, obj):
        return obj.assignments.count()

class StaffRoleSerializer(serializers.ModelSerializer):
    """Detailed serializer for staff roles"""
    created_by = MyUserSerializer(read_only=True)
    assignments_count = serializers.SerializerMethodField()
    permissions_list = serializers.ListField(
        child=serializers.CharField(),
        source='permissions',
        required=False
    )
    
    class Meta:
        model = StaffRole
        fields = '__all__'
        read_only_fields = ['profile', 'created_by']
    
    def get_assignments_count(self, obj):
        return obj.assignments.count()

class StaffGroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for staff group lists"""
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffGroup
        fields = ['id', 'name', 'description',  'users_count', 'created_at']
    
    def get_users_count(self, obj):
        return obj.users.count()

class StaffGroupSerializer(serializers.ModelSerializer):
    """Detailed serializer for staff groups"""
    created_by = MyUserSerializer(read_only=True)
    users_count = serializers.SerializerMethodField()
    permissions_list = serializers.ListField(
        child=serializers.CharField(),
        source='permissions',
        required=False
    )
    
    class Meta:
        model = StaffGroup
        fields = '__all__'
        read_only_fields = ['profile', 'created_by']
    
    def get_users_count(self, obj):
        return obj.users.count()

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

class ActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for activity logs"""
    user = MyUserSerializer(read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = '__all__'

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
        
    

