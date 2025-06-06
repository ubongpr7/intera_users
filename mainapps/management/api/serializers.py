from rest_framework import serializers
from mainapps.company.models import Company, CompanyAddress, Contact
from mainapps.inventory.models import Inventory, InventoryCategory
from mainapps.management.models import ActivityLog, CompanyProfile,CompanyProfileAddress, StaffGroup, StaffRole, StaffRoleAssignment
from rest_framework import serializers

from mainapps.orders.models import PurchaseOrder

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
        if obj.model_name=='inventory':
            return f'{Inventory.objects.get(id= obj.object_id).name}'
        elif obj.model_name=='companyprofile':
            return f'{CompanyProfile.objects.get(id= obj.object_id).name}'
        elif obj.model_name=='companyprofileaddress':
            return f'{CompanyProfileAddress.objects.get(id= obj.object_id).street}'
        elif obj.model_name=='company':
            return  f'{Company.objects.get(id= obj.object_id).name}'
        elif obj.model_name=='companyaddress':
            return  f'{CompanyAddress.objects.get(id= obj.object_id).title}'
        elif obj.model_name=='contact':
            return  f'{Contact.objects.get(id= obj.object_id).role} - {Contact.objects.get(id= obj.object_id).email}'
        elif obj.model_name=='inventorycategory':
            return  f'{InventoryCategory.objects.get(id= obj.object_id).name}'
        elif obj.model_name=='purchaseorder':
            return  PurchaseOrder.objects.get(id= obj.object_id).reference
        else:
            return obj.object_id

class StaffGroupSerializer(serializers.ModelSerializer):
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

class StaffRoleSerializer(serializers.ModelSerializer):
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
        
    