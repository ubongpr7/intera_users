import base64
from io import BytesIO

import pyotp
import qrcode
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from subapps.email_system.emails import send_html_email
from .models import User, VerificationCode
from djoser.social.views import ProviderAuthView
from django.contrib.auth import get_user_model
from mainapps.common.settings import get_company_or_profile

from .serializers import SocialJWTSerializer
from django.conf import settings
from .serializers import (
    MyUserSerializer as UserSerializer,
     UserUpdateSerializer, 
     UserQuotaMetadataSerializer,
     TokenRefreshSerializer,
     MyTokenObtainPairSerializer,
     OwnerRegistrationSerializer,
     CompanyContextSwitchSerializer,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)


def _set_session_cookies(response, access_token=None, refresh_token=None):
    if access_token:
        response.set_cookie(
            settings.AUTH_COOKIE,
            access_token,
            max_age=settings.AUTH_COOKIE_ACCESS_MAX_AGE,
            path=settings.AUTH_COOKIE_PATH,
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=settings.AUTH_COOKIE_HTTP_ONLY,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
    if refresh_token:
        response.set_cookie(
            settings.AUTH_REFRESH_COOKIE,
            refresh_token,
            max_age=settings.AUTH_COOKIE_REFRESH_MAX_AGE,
            path=settings.AUTH_COOKIE_PATH,
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=settings.AUTH_COOKIE_HTTP_ONLY,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )


def _clear_session_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE, path=settings.AUTH_COOKIE_PATH)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_COOKIE_PATH)


def _build_auth_payload(user, profile, refresh, access):
    agent = profile.agent if profile and hasattr(profile, "agent") else None
    return {
        "refresh": str(refresh),
        "access": str(access),
        "id": user.id,
        "username": user.username,
        "is_verified": getattr(user, "is_verified", False),
        "profile": str(profile.id) if profile else None,
        "profile_context": MyTokenObtainPairSerializer._profile_payload(profile, user),
        "profiles": [
            MyTokenObtainPairSerializer._profile_payload(item, user)
            for item in MyTokenObtainPairSerializer.list_accessible_profiles(user)
        ],
        "currency": profile.currency if profile else None,
        "email": user.email,
        "first_name": getattr(user, "first_name", ""),
        "model_name": agent.model_name if agent else None,
        "agent_name": agent.name if agent else "",
        "provider": agent.provider if agent else None,
    }




class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserViewSet(viewsets.ModelViewSet):
    """User management ViewSet"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', ]:
            return UserUpdateSerializer
        if self.action == 'quota_meta_data':
            return UserQuotaMetadataSerializer
        return super().get_serializer_class()    
    
    @action(detail=False, methods=['get'], url_path='quota-meta-data')
    def quota_meta_data(self, request):
        meta_data = request.user.meta_data or {}
        serializer = self.get_serializer(instance=meta_data)
        return Response(serializer.data)
    
    def get_queryset(self):
        if  not self.request.user.is_authenticated:
            return User.objects.none()
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Only staff can delete users.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Direct user self-registration is disabled."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['get', ])
    def me(self, request):
        """Get or update user profile"""
        return Response(UserSerializer(request.user).data)
    
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search users"""
        query = request.query_params.get('q', '')
        if query:
            queryset = self.get_queryset().filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query)
            ).filter(is_active=True)
            
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response([])

    @action(detail=False, methods=['post'], url_path='create-staff')
    def create_staff(self, request):
        return Response(
            {
                "detail": "Direct staff account creation is disabled. Use company invitations endpoint: POST /management/invitations/invite/."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )



class VerificationAPI(APIView):
    throttle_classes = [AnonRateThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        """Handle both sending verification code and verifying code submission (POST)"""
        action = request.data.get('action')

        if action == 'send_code':
            return self.send_verification_code(request)
        elif action == 'verify_code':
            return self.verify_code(request)
        else:
            return Response(
                {"error": "Invalid action. Use 'send_code' or 'verify_code'."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def send_verification_code(self, request):
        """Send verification code via email"""
        email = request.data.get('email')

        if not email:
            return Response(
                {"error": "Email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = User.objects.filter(email=email).first()
        if user:
            code, _ = VerificationCode.objects.get_or_create(user=user)
            code.regenerate()
            send_html_email(
                subject='Your Verification Code',
                message=f'Use this code to verify your login: {code.code}',
                to_email=[user.email],
                html_file='accounts/verify.html'
            )

        return Response(
            {"message": "If the account exists, a verification code has been sent."},
            status=status.HTTP_200_OK
        )

    def verify_code(self, request):
        """Verify code submission"""
        email = request.data.get('email')
        code_input = request.data.get('code')
        
        if not email or not code_input:
            return Response(
                {"error": "Both email and code are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        verification_code = VerificationCode.objects.filter(user=user).first()
        if not verification_code or not verification_code.is_valid():
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        if str(verification_code.code) != code_input.strip():
            verification_code.mark_failed_attempt()
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)

        verification_code.mark_successful_attempt()
        verification_code.regenerate()
        return Response(
            {
                "message": "Verification successful",
                "user_id": user.id,
                "email": user.email
            },
            status=status.HTTP_200_OK
        )


class OwnerRegistrationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = OwnerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        profile = get_company_or_profile(user)
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "profile_id": profile.id if profile else None,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomProviderAuthView(ProviderAuthView):
    serializer_class = SocialJWTSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 201:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            _set_session_cookies(response, access_token=access_token, refresh_token=refresh_token)

        return response


class CompanyContextSwitchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = CompanyContextSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = MyTokenObtainPairSerializer.resolve_active_profile(
            request.user,
            profile_id=serializer.validated_data.get("profile_id"),
            company_code=serializer.validated_data.get("company_code"),
        )
        if not profile:
            return Response(
                {"detail": "No matching company context found for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.profile_id != profile.id:
            User.objects.filter(id=request.user.id).update(profile=profile)
            request.user.profile = profile

        auth = getattr(request, "auth", None)
        mfa_verified = bool(auth.payload.get("mfa_verified")) if auth is not None and hasattr(auth, "payload") else False
        refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            request.user,
            profile,
            mfa_verified=mfa_verified,
        )
        payload = _build_auth_payload(request.user, profile, refresh, access)
        response = Response(payload, status=status.HTTP_200_OK)
        _set_session_cookies(response, access_token=str(access), refresh_token=str(refresh))
        return response


class CompanyMembershipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profiles = MyTokenObtainPairSerializer.list_accessible_profiles(request.user)
        profile_map = {str(profile.id): profile for profile in profiles}

        active_profile = None
        auth = getattr(request, "auth", None)
        token_profile_id = None
        if auth is not None and hasattr(auth, "payload"):
            token_profile_id = auth.payload.get("profile_id")
        if token_profile_id:
            active_profile = profile_map.get(str(token_profile_id))
        if not active_profile and request.user.profile_id:
            active_profile = profile_map.get(str(request.user.profile_id))

        return Response(
            {
                "active_profile_id": str(active_profile.id) if active_profile else None,
                "profiles": [
                    MyTokenObtainPairSerializer._profile_payload(profile, request.user)
                    for profile in profiles
                ],
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            _set_session_cookies(response, access_token=access_token, refresh_token=refresh_token)

        return response


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)

        if refresh_token:
            request.data['refresh'] = refresh_token

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get('access')
            maybe_refresh_token = response.data.get('refresh')
            _set_session_cookies(
                response,
                access_token=access_token,
                refresh_token=maybe_refresh_token if maybe_refresh_token else None,
            )

        return response


class CustomTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        access_token = request.COOKIES.get(settings.AUTH_COOKIE)

        if access_token:
            request.data['token'] = access_token

        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_session_cookies(response)
        return response

class MfaSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        force = str(request.data.get('force', '')).strip().lower() in {'1', 'true', 'yes'}

        if user.mfa_enabled and not force and user.has_setup_mfa:
            return Response(
                {"detail": "MFA is already enabled for this account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if force or not user.mfa_secret:
            user.mfa_secret = pyotp.random_base32()
            user.mfa_enabled = False
            user.save(update_fields=['mfa_secret', 'mfa_enabled'])

        issuer = getattr(settings, "MFA_ISSUER", "Intera")
        totp = pyotp.TOTP(user.mfa_secret)
        otpauth_url = totp.provisioning_uri(name=user.email, issuer_name=issuer)

        qr_image = qrcode.make(otpauth_url)
        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        qr_data = base64.b64encode(buffer.getvalue()).decode("ascii")

        return Response(
            {
                "mfa_secret": user.mfa_secret,
                "otpauth_url": otpauth_url,
                "qr_code": f"data:image/png;base64,{qr_data}",
                "mfa_enabled": user.mfa_enabled,
                "has_setup_mfa": user.has_setup_mfa,
            },
            status=status.HTTP_200_OK
        )


class MfaVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        code = (request.data.get('code') or '').strip()

        if not code:
            return Response(
                {"detail": "Verification code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.mfa_secret:
            return Response(
                {"detail": "MFA has not been set up for this account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"detail": "Invalid verification code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.mfa_enabled or not user.has_setup_mfa:
            user.mfa_enabled = True
            user.has_setup_mfa = True
            user.save(update_fields=['mfa_enabled', 'has_setup_mfa'])
        auth = getattr(request, "auth", None)
        token_profile_id = None
        if auth is not None and hasattr(auth, "payload"):
            token_profile_id = auth.payload.get("profile_id")
        profile = MyTokenObtainPairSerializer.resolve_active_profile(
            user,
            profile_id=token_profile_id if token_profile_id else None,
        )
        if profile and user.profile_id != profile.id:
            User.objects.filter(id=user.id).update(profile=profile)
            user.profile = profile

        refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            user,
            profile,
            mfa_verified=True,
        )
        payload = _build_auth_payload(user, profile, refresh, access)
        payload.update({
            "detail": "MFA verified successfully.",
            "mfa_enabled": True,
            "has_setup_mfa": user.has_setup_mfa,
        })
        response = Response(payload, status=status.HTTP_200_OK)
        _set_session_cookies(response, access_token=str(access), refresh_token=str(refresh))
        return response


class MfaToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        desired = request.data.get('enabled', None)

        if desired is None:
            desired = not user.mfa_enabled
        else:
            desired = str(desired).strip().lower() in {'1', 'true', 'yes'}

        if desired and user.mfa_enabled:
            return Response(
                {"detail": "MFA is already enabled for this account.", "mfa_enabled": True},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not desired and not user.mfa_enabled:
            return Response(
                {"detail": "MFA is already disabled for this account.", "mfa_enabled": False},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.mfa_secret:
            return Response(
                {"detail": "MFA has not been set up for this account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        code = (request.data.get('code') or '').strip()
        if not code:
            return Response(
                {"detail": "Verification code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"detail": "Invalid verification code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.mfa_enabled = desired
        if desired:
            user.has_setup_mfa = True
        user.save(update_fields=['mfa_enabled', 'has_setup_mfa'])

        state = "enabled" if desired else "disabled"
        return Response(
            {"detail": f"MFA {state} successfully.", "mfa_enabled": user.mfa_enabled},
            status=status.HTTP_200_OK
        )
