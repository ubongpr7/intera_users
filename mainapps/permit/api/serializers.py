from rest_framework import serializers
from mainapps.accounts.models import User
from mainapps.profile.models import StaffGroup, StaffRole, StaffRoleAssignment
from mainapps.permit.models import CustomUserPermission, PlatformChoices

class PermissionDetailSerializer(serializers.ModelSerializer):
    has_permission = serializers.BooleanField(read_only=True)
    category = serializers.StringRelatedField()

    class Meta:
        model = CustomUserPermission
        fields = ('platform', 'codename', 'name', 'description', 'category', 'has_permission')


class UserPermissionUpdateSerializer(serializers.ModelSerializer):
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        required=False,
        default=PlatformChoices.INTERA_IMS,
        write_only=True,
    )
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = User
        fields = ('platform', 'permissions',)

class GroupPermissionUpdateSerializer(serializers.ModelSerializer):
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        required=False,
        default=PlatformChoices.INTERA_IMS,
        write_only=True,
    )
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = StaffGroup
        fields = ('platform', 'permissions',)
class RolePermissionUpdateSerializer(serializers.ModelSerializer):
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        required=False,
        default=PlatformChoices.INTERA_IMS,
        write_only=True,
    )
    permissions = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = StaffRole
        fields = ('platform', 'permissions',)




class GroupDetailSerializer(serializers.ModelSerializer):
    belongs_to = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffGroup
        fields = ('id', 'name', 'platform', 'is_system', 'belongs_to')


class UserGroupUpdateSerializer(serializers.ModelSerializer):
    platform = serializers.ChoiceField(
        choices=PlatformChoices.choices,
        required=False,
        default=PlatformChoices.INTERA_IMS,
        write_only=True,
    )
    groups = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        help_text="List of permission codenames to assign"
    )

    class Meta:
        model = User
        fields = ('platform', 'groups',)


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=StaffRole.objects.all(),
        write_only=True,
        help_text="ID of the role to assign"
    )

    class Meta:
        model = StaffRoleAssignment
        fields = '__all__'
        read_only_fields = ('id', 'profile', 'assigned_at','assigned_by')
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
