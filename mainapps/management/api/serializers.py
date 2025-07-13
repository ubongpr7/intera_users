from rest_framework import serializers
from mainapps.management.models import ActivityLog, CompanyProfile,CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment
from rest_framework import serializers


class CompanyAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfileAddress
        fields = '__all__'
        read_only_fields = ['id']

class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = '__all__'
        read_only_fields = ['id', 'is_verified', 'verification_date', 'created_at', 'updated_at']


class ActivityUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()

class ActivityLogSerializer(serializers.ModelSerializer):
    user = ActivityUserSerializer()
    action = serializers.CharField(source='get_action_display')
    model_identifier = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'user',
            'action',
            'model_name',
            'object_id',
            'timestamp',
            'details',
            'model_identifier'
        ]
        read_only_fields = fields

        
    def get_model_identifier(self, obj):
        return obj.object_id

class APIStaffGroupSerializer(serializers.ModelSerializer):
    permission_num=serializers.SerializerMethodField()
    users_num=serializers.SerializerMethodField()
    class Meta:
        model = StaffGroup
        fields = ['id','name','description','users_num','permission_num']
        read_only_fields = ['id','users_num','permission_num']
        
    def get_users_num(self,obj):
        if obj.users.count():
            return obj.users.count()
        return 0
    def get_permission_num(self,obj):
        if obj.permissions.count():
            return obj.permissions.count()
        return 0

class APIStaffRoleSerializer(serializers.ModelSerializer):
    permission_num=serializers.SerializerMethodField()
    users_num=serializers.SerializerMethodField()

    class Meta:
        model = StaffRole
        fields = ['id','name','description','users_num','permission_num']
        read_only_fields = ['id','users_num','permission_num']
        
    def get_users_num(self,obj):
            return obj.assignments.count()
    def get_permission_num(self,obj):
        if obj.permissions.count():
            return obj.permissions.count()
    
class StaffRoleAssignmentSerializer(serializers.ModelSerializer):
    role_name=serializers.CharField(source='role.name',read_only=True)
    class Meta:
        model = StaffRoleAssignment
        fields = ['id','role_name','is_active','role','start_date','end_date']
        read_only_fields = ['id']
        
    