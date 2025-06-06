from rest_framework import serializers
from mainapps.accounts.models import User
from mainapps.management.models import StaffGroup, StaffRole, StaffRoleAssignment
from mainapps.permit.models import CustomUserPermission

class PermissionDetailSerializer(serializers.ModelSerializer):
    has_permission = serializers.BooleanField(read_only=True)
    category = serializers.StringRelatedField()

    class Meta:
        model = CustomUserPermission
        fields = ('codename', 'name', 'description', 'category', 'has_permission')


class UserPermissionUpdateSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = User
        fields = ('permissions',)

class GroupPermissionUpdateSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = StaffGroup
        fields = ('permissions',)
class RolePermissionUpdateSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = StaffRole
        fields = ('permissions',)




class GroupDetailSerializer(serializers.ModelSerializer):
    belongs_to = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffGroup
        fields = ('id', 'name',  'belongs_to')


class UserGroupUpdateSerializer(serializers.ModelSerializer):
    groups = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = User
        fields = ('groups',)


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=StaffRole.objects.all(),
        write_only=True,
        help_text="ID of the role to assign"
    )

    class Meta:
        model = StaffRoleAssignment
        fields = '__all__'
        read_only_fields = ('id', 'assigned_at','assigned_by')
        extra_kwargs = {
            'role': {'required': True},
            'user': {'required': True}
        }
    def create(self, validated_data):
        user = validated_data.pop('user')
        role = validated_data.pop('role')
        assigned_by = self.context['request'].user
        profile = self.context['request'].user.profile
        
        instance = StaffRoleAssignment.objects.create(
            user=user,
            role=role,
            profile=profile,
            assigned_by=assigned_by,
            **validated_data
        )
        return instance
    