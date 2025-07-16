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
                 'is_staff', 'groups', 'user_permissions','date_joined', 'is_active', ]
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
    

    @classmethod
    def get_all_permissions(self,user):
        user_perms=set()

        user_perms.update(user.custom_permissions.all().values_list('codename', flat=True))
        try:
            from django.utils import timezone
            current_time = timezone.now()
            for role in user.roles.all().iterator():
                if role.start_date and role.end_date:
                    
                    if role.end_date < current_time:
                        role.delete()
                    else:
                        perms = role.role.permissions.all().values_list('codename', flat=True)
                        user_perms.update(perms)
        except Exception as e:
            print(f"Error: {e}")
        try:
            groups=user.staff_groups.all()
            for group in groups:
                user_perms.update(group.permissions.all().values_list('codename', flat=True))
        except Exception as e:
            print(e)
        print('user_perms: ', user_perms)
        return user_perms
    
    @classmethod
    def get_token(self,user):
        token =super().get_token(user)
        perms= self.get_all_permissions(user)
        token['permissions']=list(perms)
        profile_id= user.profile.id if user.profile else None
        token['profile_id']=profile_id
        owner_id=None
        if user.profile:
            owner_id = user.profile.owner.id
            token['owner_id']=owner_id
        return token



    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user  
        data.update({
            'id': user.id,
            'username': user.username,
            'is_worker': user.is_worker,
            'is_main': user.is_main,
            'is_verified': user.is_verified,
            'profile': user.profile.id if user.profile else None,
            'currency': user.profile.currency if user.profile else None,
            'email': user.email,
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
