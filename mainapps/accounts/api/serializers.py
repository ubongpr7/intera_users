from rest_framework import serializers,exceptions
from rest_framework.validators import UniqueValidator
from mainapps.accounts.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from mainapps.management.api.serializers import StaffRoleAssignmentSerializer
from mainapps.permit.models import CustomUserPermission

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
        re_password = validated_data.pop("re_password", None)
        
        user = User.objects.create_user(**validated_data)
        user.is_main=True
        user.save()

    

        return user

class StaffUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField( required=True,)

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password','phone',)
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        
        user = User.objects.create_user(**validated_data)
        user.is_main=False
        user.is_worker=True
        user.save()

    

        return user


class LogoutSerializer(serializers.Serializer):
    refresh=serializers.CharField()

class MyUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        exclude = ['last_login', 'is_superuser','is_verified', 'is_main', 'is_worker', 
                 'is_staff', 'groups', 'user_permissions','date_joined', 'is_active']
        # read_only_fields = []
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }
    
    def get_roles(self, obj):
        active_assignments = obj.roles.filter(is_active=True)
        return StaffRoleAssignmentSerializer(active_assignments, many=True).data
    
class UserPictureSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=("picture",)
    
class VerificationSerializer(serializers.Serializer):
    code=serializers.IntegerField()
    
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user  
        try:
            company_id = user.company.id
        except user._meta.get_field("company").related_model.DoesNotExist:
            company_id = None
        data.update({
            'id': user.id,
            'username': user.username,
            'is_worker': user.is_worker,
            'is_main': user.is_main,
            'is_verified': user.is_verified,
            'profile': user.profile.id if user.profile else None,
            'email': user.email,
            'company': company_id,
            'first_name': user.first_name,
        })
        
        return data 
    
           


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
