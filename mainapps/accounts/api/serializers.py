from rest_framework import serializers
from mainapps.accounts.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from mainapps.profile.api.serializers import StaffRoleAssignmentSerializer
from mainapps.permit.models import CustomUserPermission
from mainapps.accounts.serializers import MyTokenObtainPairSerializer as CoreTokenObtainPairSerializer

from django.contrib.auth.password_validation import validate_password


class RootUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True,)
    re_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password', 're_password')
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        validated_data.pop("re_password", None)
        return User.objects.create_user(**validated_data)
    
    def validate(self, attrs):
        password = attrs.get("password")
        re_password = attrs.get("re_password")
        if password != re_password:
            raise serializers.ValidationError({"re_password": "Passwords do not match"})
        validate_password(password)
        return attrs

class StaffUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password','phone',)
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    
    def validate(self, attrs):
        validate_password(attrs.get("password"))
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh=serializers.CharField()

class MyUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone', 'picture', 'sex',
            'is_verified', 'is_staff',
            'date_of_birth', 'profile', 'custom_permissions', 'roles',
        ]
        read_only_fields = ['id', 'is_verified', 'is_staff']
        extra_kwargs = {'email': {'required': True}}
    
    def get_roles(self, obj):
        active_assignments = obj.roles.filter(is_active=True)
        return StaffRoleAssignmentSerializer(active_assignments, many=True).data
    
class UserPictureSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=("picture",)
    
class VerificationSerializer(serializers.Serializer):
    code=serializers.IntegerField()
    
class MyTokenObtainPairSerializer(CoreTokenObtainPairSerializer):
    pass


class UserPermissionSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True,
        slug_field='codename',
        queryset=CustomUserPermission.objects.all(),
        source='custom_permissions'
    )

    class Meta:
        model = User
        fields = ('permissions',)
        extra_kwargs = {
            'permissions': {
                'help_text': 'List of permission codenames to assign to the user'
            }
        }
