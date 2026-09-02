from rest_framework import serializers
from mainapps.accounts.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from mainapps.profile.api.serializers import StaffRoleAssignmentSerializer
from mainapps.permit.models import CustomUserPermission
from mainapps.accounts.serializers import MyTokenObtainPairSerializer as CoreTokenObtainPairSerializer
from mainapps.accounts.legal import record_signup_consents, validate_signup_consents

from django.contrib.auth.password_validation import validate_password


def _resolve_referrer(attrs):
    code = (attrs.get('referral_code') or '').strip().upper()
    attrs['referral_code'] = code
    if not code:
        attrs['referrer_user'] = None
        return attrs
    referrer = User.objects.filter(referral_code__iexact=code).first()
    if referrer is None:
        raise serializers.ValidationError({'referral_code': 'Referral code is invalid.'})
    attrs['referrer_user'] = referrer
    return attrs


class RootUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True,)
    re_password = serializers.CharField(write_only=True, required=True)
    terms_accepted = serializers.BooleanField(write_only=True, required=True)
    privacy_accepted = serializers.BooleanField(write_only=True, required=True)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'first_name', 'email', 'password', 're_password',
            'terms_accepted', 'privacy_accepted', 'referral_code',
        )
        extra_kwargs = {
            'first_name': {'required': True},
            'email': {'required': True}
        }


    def create(self, validated_data):
        validated_data.pop("re_password", None)
        referrer = validated_data.pop('referrer_user', None)
        validated_data.pop('referral_code', None)
        user = User.objects.create_user(**validated_data)
        if referrer is not None:
            user.referred_by = referrer
            user.save(update_fields=['referred_by'])
        record_signup_consents(user, request=self.context.get("request"), source="root_signup")
        return user
    
    def validate(self, attrs):
        attrs = validate_signup_consents(attrs)
        password = attrs.get("password")
        re_password = attrs.get("re_password")
        if password != re_password:
            raise serializers.ValidationError({"re_password": "Passwords do not match"})
        validate_password(password)
        return _resolve_referrer(attrs)

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
            'date_of_birth', 'profile', 'custom_permissions', 'roles', 'referral_code',
        ]
        read_only_fields = ['id', 'is_verified', 'is_staff']
        extra_kwargs = {'email': {'required': True}}
        ref_name = "AccountsApiMyUser"
    
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
