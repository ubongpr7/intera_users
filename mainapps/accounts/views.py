import base64
import secrets
from datetime import timedelta
from io import BytesIO

import pyotp
import qrcode
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.db.models import Q
from django.db.models import Sum
from decimal import Decimal
from urllib.parse import quote
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from subapps.email_system.emails import send_html_email
from subapps.utils.request_context import build_frontend_url, get_request_profile_id
from mainapps.permit.permit import HasModelRequestPermission
from .models import AffiliatePartner, AffiliatePartnerInvitation, PlatformStaffInvitation, ReferralPayout, User, VerificationCode
from .legal import (
    PRIVACY_POLICY_VERSION,
    TERMS_POLICY_VERSION,
    record_signup_consents,
)
from djoser.social.views import ProviderAuthView
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from mainapps.common.settings import get_company_or_profile
from mainapps.profile.models import CompanyMembership, CompanyProfile, SupportAccessGrant
from mainapps.permit.models import PlatformChoices
from subapps.kafka.producers import (
    build_actor,
    publish_support_access_workspace_entered,
    publish_support_access_workspace_exited,
)

from .serializers import SocialJWTSerializer
from .authorization_context import (
    authorization_context_from_request,
    issue_authorization_context,
    issue_websocket_ticket,
    public_signing_jwks,
    websocket_ticket_lifetime_seconds,
)
from django.conf import settings
from django.core.cache import cache
from .serializers import (
    MyUserSerializer,
    MyUserSerializer as UserSerializer,
    UserUpdateSerializer,
    UserQuotaMetadataSerializer,
    TokenRefreshSerializer,
    MyTokenObtainPairSerializer,
    OwnerRegistrationSerializer,
    CompanyContextSwitchSerializer,
    AffiliatePartnerSerializer,
    ReferralPayoutSerializer,
)
from .emails import send_affiliate_notification
from .affiliate import affiliate_agreement_terms, affiliate_partner_for_user, commission_rate_percent, sync_affiliate_account_user
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)


class WebSocketTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            "Issue a short-lived WebSocket ticket bound to the bearer token and "
            "X-Intera-Authorization-Context pair."
        ),
        responses={
            status.HTTP_201_CREATED: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                required=["ws_ticket", "expires_in"],
                properties={
                    "ws_ticket": openapi.Schema(type=openapi.TYPE_STRING),
                    "expires_in": openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1),
                    "ticket": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Deprecated compatibility alias for ws_ticket.",
                    ),
                },
            )
        },
    )
    def post(self, request):
        context = authorization_context_from_request(request)
        ticket = issue_websocket_ticket(context)
        return Response(
            {
                "ws_ticket": ticket,
                "expires_in": websocket_ticket_lifetime_seconds(),
                "ticket": ticket,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicSigningKeysView(APIView):
    """Publish the current RSA verification key for device-proof validation."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "Return the public JSON Web Key used to verify authorization contexts, "
            "WebSocket tickets, and short-lived device-enrolment proofs."
        ),
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT)},
    )
    def get(self, _request):
        try:
            payload = public_signing_jwks()
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = Response(payload)
        response["Cache-Control"] = "public, max-age=300"
        return response


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
            domain=settings.AUTH_COOKIE_DOMAIN,
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
            domain=settings.AUTH_COOKIE_DOMAIN,
        )


def _clear_session_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE, path=settings.AUTH_COOKIE_PATH, domain=settings.AUTH_COOKIE_DOMAIN)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_COOKIE_PATH, domain=settings.AUTH_COOKIE_DOMAIN)


def _build_auth_payload(
    user,
    profile,
    refresh,
    access,
    *,
    support_grant=None,
    platform=PlatformChoices.INTERA_IMS,
):
    return {
        "refresh": str(refresh),
        "access": str(access),
        "authorization_context": issue_authorization_context(
            user,
            profile=profile,
            support_grant=support_grant,
            platform=platform,
            access_token_id=access.get("jti"),
        ),
        "id": user.id,
        "username": user.username,
        "is_verified": getattr(user, "is_verified", False),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "is_affiliate_marketer": bool(getattr(user, "is_affiliate_marketer", False)),
        "profile": str(profile.id) if profile else None,
        "profile_context": MyTokenObtainPairSerializer._profile_payload(
            profile,
            user,
            support_grant=support_grant,
        ),
        "profiles": [
            MyTokenObtainPairSerializer._profile_payload(
                item.profile,
                user,
                support_grant=item.support_grant,
            )
            for item in MyTokenObtainPairSerializer.list_accessible_profile_contexts(user)
        ],
        "currency": profile.currency if profile else None,
        "email": user.email,
        "first_name": getattr(user, "first_name", ""),
        "platform": platform,
    }


def _get_request_support_grant(request):
    auth = getattr(request, "auth", None)
    support_access_grant_id = None
    if auth is not None and hasattr(auth, "payload"):
        support_access_grant_id = auth.payload.get("support_access_grant_id")
    if not support_access_grant_id:
        return None
    return (
        SupportAccessGrant.objects.select_related(
            "profile",
            "grantee_user",
            "created_by",
            "approved_by",
            "revoked_by",
        )
        .prefetch_related("custom_permissions")
        .filter(id=support_access_grant_id)
        .first()
    )


def _issue_email_verification_code(user, *, subject, message):
    code, _ = VerificationCode.objects.get_or_create(user=user)
    code.regenerate()
    send_html_email(
        subject=subject,
        message=message.format(code=code.code),
        to_email=[user.email],
        html_file='accounts/verify.html'
    )
    return code


def _consume_email_verification_code(user, code_input):
    verification_code = VerificationCode.objects.filter(user=user).first()
    if not verification_code or not verification_code.is_valid():
        return False

    if str(verification_code.code) != code_input.strip():
        verification_code.mark_failed_attempt()
        return False

    verification_code.mark_successful_attempt()
    verification_code.regenerate()
    return True


def _build_mfa_verified_response(request, user):
    auth = getattr(request, "auth", None)
    token_profile_id = None
    token_support_grant_id = None
    token_platform = PlatformChoices.INTERA_IMS
    if auth is not None and hasattr(auth, "payload"):
        token_profile_id = auth.payload.get("profile_id")
        token_support_grant_id = auth.payload.get("support_access_grant_id")
        token_platform = auth.payload.get("platform", PlatformChoices.INTERA_IMS)
    profile_access = MyTokenObtainPairSerializer.resolve_active_profile_access(
        user,
        profile_id=token_profile_id if token_profile_id else None,
        support_access_grant_id=token_support_grant_id,
    )
    profile = profile_access.profile
    if profile and user.profile_id != profile.id:
        User.objects.filter(id=user.id).update(profile=profile)
        user.profile = profile

    refresh, access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
        user,
        profile,
        mfa_verified=True,
        support_grant=profile_access.support_grant,
        platform=token_platform,
    )
    payload = _build_auth_payload(
        user,
        profile,
        refresh,
        access,
        support_grant=profile_access.support_grant,
        platform=token_platform,
    )
    payload.update({
        "detail": "MFA verified successfully.",
        "mfa_enabled": True,
        "has_setup_mfa": user.has_setup_mfa,
    })
    response = Response(payload, status=status.HTTP_200_OK)
    _set_session_cookies(response, access_token=str(access), refresh_token=str(refresh))
    return response




class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserViewSet(viewsets.ModelViewSet):
    """User management ViewSet"""
    ADMIN_ACTIONS = {"list", "retrieve", "update", "partial_update", "destroy", "search", "create_staff"}
    PERSONAL_ACTIONS = {"me", "partial_update_me", "quota_meta_data", "referrals"}

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    required_permission = "manage_company_settings"
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if getattr(self, "action", None) in {"admin_me", "admin_summary"}:
            return [IsAdminUser()]
        if getattr(self, "action", None) in self.PERSONAL_ACTIONS:
            return [IsAuthenticated()]
        if getattr(self, "action", None) in self.ADMIN_ACTIONS:
            return [IsAuthenticated(), HasModelRequestPermission()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', ]:
            return UserUpdateSerializer
        if self.action == 'quota_meta_data':
            return UserQuotaMetadataSerializer
        return super().get_serializer_class()    
    
    @action(detail=False, methods=['get'], url_path='quota-meta-data')
    def quota_meta_data(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None and getattr(request.user, "profile_id", None):
            profile = CompanyProfile.objects.filter(id=request.user.profile_id).first()
        meta_data = MyTokenObtainPairSerializer._subscription_metadata(profile) if profile else {}
        serializer = self.get_serializer(instance=meta_data)
        return Response(serializer.data)
    
    def get_queryset(self):
        if  not self.request.user.is_authenticated:
            return User.objects.none()
        if self.request.user.is_staff:
            return User.objects.all()
        if getattr(self, "action", None) in self.ADMIN_ACTIONS:
            profile_id = get_request_profile_id(self.request, as_str=False)
            if profile_id:
                return User.objects.filter(profile_id=profile_id)
        return User.objects.filter(id=self.request.user.id)

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target.pk == request.user.pk:
            raise PermissionDenied('You cannot delete your own administrator account.')
        if target.is_superuser and not request.user.is_superuser:
            raise PermissionDenied('Only a superuser can delete another superuser.')
        return super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Direct user self-registration is disabled."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Return the authenticated user's personal profile."""
        return Response(MyUserSerializer(request.user).data)

    @action(detail=False, methods=['get'], url_path='admin-me')
    def admin_me(self, request):
        """Return the minimal identity used by the isolated staff portal."""
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': bool(user.is_staff),
            'is_superuser': bool(user.is_superuser),
        })

    @action(detail=False, methods=['get'], url_path='admin-summary')
    def admin_summary(self, request):
        """Return platform-level identity and workspace counts for staff insight dashboards."""
        users = User.objects.all()
        profiles = CompanyProfile.objects.all()
        memberships = CompanyMembership.objects.all()
        return Response({
            'generated_at': timezone.now().isoformat(),
            'users': {
                'total': users.count(),
                'active': users.filter(is_active=True).count(),
                'staff': users.filter(is_staff=True, is_active=True).count(),
                'superusers': users.filter(is_superuser=True, is_active=True).count(),
            },
            'workspaces': {
                'total': profiles.count(),
                'verified': profiles.filter(is_verified=True).count(),
            },
            'memberships': {
                'active': memberships.filter(is_active=True).count(),
            },
        })

    @me.mapping.patch
    def partial_update_me(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MyUserSerializer(request.user).data)

    @action(detail=False, methods=['get'])
    def referrals(self, request):
        user = request.user
        partner = affiliate_partner_for_user(user)
        if partner is not None:
            if partner.account_user_id != user.pk:
                AffiliatePartner.objects.filter(pk=partner.pk).update(account_user=user)
                partner.account_user = user
            sync_affiliate_account_user(partner, user)
        payouts = (
            partner.payouts.select_related('referred_user').order_by('-created_at')
            if partner
            else user.referral_payouts.select_related('referred_user').order_by('-created_at')
        )
        if partner:
            referred_queryset = partner.referred_users
            if partner.account_user_id:
                referred_queryset = referred_queryset.exclude(pk=partner.account_user_id)
        else:
            referred_queryset = user.referred_users
        referred_users = (
            referred_queryset.order_by('-date_joined')[:100]
        )
        referral_code = partner.code if partner else user.referral_code
        commission_rate = partner.commission_rate if partner else user.referral_commission_rate

        def total_for(queryset):
            return queryset.aggregate(total=Sum('payout_amount')).get('total') or Decimal('0.00')

        public_base = (getattr(settings, 'INTERA_IMS_FRONTEND_SITE_URL', '') or getattr(settings, 'FRONTEND_SITE_URL', '')).rstrip('/')
        referral_url = f"{public_base}/accounts?ref={quote(referral_code)}" if public_base else build_frontend_url(request, f"/accounts?ref={quote(referral_code)}")
        return Response({
            'referral_code': referral_code,
            'referral_url': referral_url,
            'commission_rate': str(commission_rate),
            'commission_rate_display': commission_rate_percent(commission_rate),
            'referred_count': referred_queryset.count(),
            'referred_users': [
                {
                    'id': referred.id,
                    'email': referred.email,
                    'first_name': referred.first_name,
                    'last_name': referred.last_name,
                    'joined_at': referred.date_joined.isoformat() if referred.date_joined else None,
                }
                for referred in referred_users
            ],
            'earnings': {
                'total': str(total_for(payouts)),
                'pending': str(total_for(payouts.filter(status=ReferralPayout.Status.PENDING))),
                'paid': str(total_for(payouts.filter(status=ReferralPayout.Status.PAID))),
            },
            'payouts': [
                {
                    'id': payout.id,
                    'payment_reference': payout.payment_reference,
                    'payment_amount': str(payout.payment_amount),
                    'commission_amount': str(payout.payout_amount),
                    'currency': payout.currency,
                    'status': payout.status,
                    'plan_slug': payout.plan_slug,
                    'created_at': payout.created_at.isoformat(),
                }
                for payout in payouts[:100]
            ],
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response([])
        queryset = self.get_queryset().filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).filter(is_active=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['post'], url_path='create-staff')
    def create_staff(self, request):
        return Response(
            {
                "detail": "Direct staff account creation is disabled. Use company invitations endpoint: POST /management/invitations/invite/."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class PlatformStaffInvitationView(APIView):
    """Platform-level staff invitations; deliberately independent of workspaces."""
    permission_classes = [IsAdminUser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only a superuser can manage platform staff invitations.")

    def get(self, request):
        invitations = PlatformStaffInvitation.objects.select_related("invited_by", "accepted_user").all()[:100]
        return Response([self._serialize(item) for item in invitations])

    def post(self, request):
        email = PlatformStaffInvitation.normalize_email(request.data.get("email"))
        try:
            validate_email(email)
        except DjangoValidationError:
            return Response({"detail": "A valid email address is required."}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email, is_staff=True).exists():
            return Response({"detail": "This user is already platform staff."}, status=status.HTTP_409_CONFLICT)
        pending = PlatformStaffInvitation.objects.filter(email__iexact=email, status=PlatformStaffInvitation.Status.PENDING).first()
        if pending and pending.expires_at > timezone.now():
            return Response({"detail": "A pending invitation already exists for this email."}, status=status.HTTP_409_CONFLICT)
        if pending:
            pending.status = PlatformStaffInvitation.Status.EXPIRED
            pending.save(update_fields=["status"])
        raw_token = secrets.token_urlsafe(32)
        invitation = PlatformStaffInvitation.objects.create(
            email=email,
            token_hash=PlatformStaffInvitation.hash_token(raw_token),
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        accept_url = self._frontend_url(request, raw_token)
        send_html_email(
            subject="You have been invited to Intera IMS administration",
            message=f"You have been invited to become an Intera IMS staff administrator. Accept the invitation: {accept_url}",
            to_email=[email],
            html_file="emails/platform_staff_invitation.html",
            from_email=getattr(settings, "EMAIL_ACCOUNTS_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            context={"accept_url": accept_url, "expires_at": invitation.expires_at, "recipient_email": email, "invited_by_email": request.user.email},
        )
        return Response(self._serialize(invitation), status=status.HTTP_201_CREATED)

    @staticmethod
    def _frontend_url(request, token):
        base = (getattr(settings, "ADMIN_FRONTEND_SITE_URL", "") or "").rstrip("/")
        if not base:
            base = build_frontend_url(request, "/").rstrip("/")
        return f"{base}/accounts/admin-invite/{quote(token, safe='')}"

    @staticmethod
    def _serialize(invitation):
        return {
            "id": str(invitation.id),
            "email": invitation.email,
            "status": invitation.status,
            "expires_at": invitation.expires_at.isoformat(),
            "created_at": invitation.created_at.isoformat(),
            "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
        }


class PlatformStaffInvitationRevokeView(APIView):
    permission_classes = [IsAdminUser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only a superuser can manage platform staff invitations.")

    def post(self, request, invitation_id):
        invitation = PlatformStaffInvitation.objects.filter(pk=invitation_id).first()
        if not invitation:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
        if invitation.status == PlatformStaffInvitation.Status.PENDING:
            invitation.status = PlatformStaffInvitation.Status.REVOKED
            invitation.save(update_fields=["status"])
        return Response(PlatformStaffInvitationView._serialize(invitation))


class PlatformStaffInvitationLookupView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = str(request.query_params.get("token") or "")
        invitation = PlatformStaffInvitation.objects.filter(token_hash=PlatformStaffInvitation.hash_token(token)).first()
        if not invitation or invitation.status != PlatformStaffInvitation.Status.PENDING:
            return Response({"detail": "Invitation is invalid or no longer available."}, status=status.HTTP_404_NOT_FOUND)
        if invitation.expires_at <= timezone.now():
            invitation.status = PlatformStaffInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            return Response({"detail": "Invitation has expired."}, status=status.HTTP_410_GONE)
        return Response({"email": invitation.email, "expires_at": invitation.expires_at.isoformat()})


class PlatformStaffInvitationAcceptView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = str(request.data.get("token") or "")
        first_name = str(request.data.get("first_name") or "").strip()
        last_name = str(request.data.get("last_name") or "").strip()
        password = request.data.get("password")
        with transaction.atomic():
            invitation = PlatformStaffInvitation.objects.select_for_update().filter(token_hash=PlatformStaffInvitation.hash_token(token)).first()
            if not invitation or invitation.status != PlatformStaffInvitation.Status.PENDING:
                return Response({"detail": "Invitation is invalid or no longer available."}, status=status.HTTP_400_BAD_REQUEST)
            if invitation.expires_at <= timezone.now():
                invitation.status = PlatformStaffInvitation.Status.EXPIRED
                invitation.save(update_fields=["status"])
                return Response({"detail": "Invitation has expired."}, status=status.HTTP_410_GONE)
            if not first_name:
                return Response({"detail": "First name is required."}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(email__iexact=invitation.email).first()
            if user is None:
                if not password:
                    return Response({"detail": "Password is required for a new account."}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    validate_password(password, user)
                except DjangoValidationError as error:
                    return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
                user = User.objects.create_user(invitation.email, password=password, first_name=first_name, last_name=last_name, is_staff=True)
            else:
                user.is_staff = True
                if not user.first_name:
                    user.first_name = first_name
                if last_name and not user.last_name:
                    user.last_name = last_name
                user.save(update_fields=["is_staff", "first_name", "last_name"])
            invitation.status = PlatformStaffInvitation.Status.ACCEPTED
            invitation.accepted_user = user
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["status", "accepted_user", "accepted_at"])
        return Response({"detail": "Staff invitation accepted. Sign in through the admin portal.", "email": user.email}, status=status.HTTP_200_OK)


class AffiliatePartnerViewSet(viewsets.ModelViewSet):
    queryset = AffiliatePartner.objects.select_related('created_by').all()
    serializer_class = AffiliatePartnerSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None
    search_fields = ('name', 'code')
    ordering_fields = ('name', 'code', 'created_at', 'updated_at')
    ordering = ('name',)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            response = super().create(request, *args, **kwargs)
            partner = AffiliatePartner.objects.get(pk=response.data['id'])
            account_user = User.objects.filter(email__iexact=partner.email).first()
            if account_user is None:
                account_user = User.objects.create_user(
                    partner.email,
                    password=None,
                    is_affiliate_marketer=True,
                )
            elif not account_user.is_affiliate_marketer:
                account_user.is_affiliate_marketer = True
                account_user.save(update_fields=['is_affiliate_marketer'])
            sync_affiliate_account_user(partner, account_user)
            partner.account_user = account_user
            partner.save(update_fields=['account_user', 'updated_at'])

        raw_token = secrets.token_urlsafe(32)
        pending = AffiliatePartnerInvitation.objects.filter(
            partner=partner,
            status=AffiliatePartnerInvitation.Status.PENDING,
        ).first()
        if pending:
            pending.status = AffiliatePartnerInvitation.Status.REVOKED
            pending.save(update_fields=['status'])
        invitation = AffiliatePartnerInvitation.objects.create(
            partner=partner,
            email=partner.email,
            token_hash=AffiliatePartnerInvitation.hash_token(raw_token),
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        public_base = (getattr(settings, 'INTERA_IMS_FRONTEND_SITE_URL', '') or getattr(settings, 'FRONTEND_SITE_URL', '')).rstrip('/')
        invite_url = f"{public_base}/accounts/affiliate-invite/{quote(raw_token, safe='')}"
        commission_rate_display = commission_rate_percent(partner.commission_rate)
        agreement_terms = affiliate_agreement_terms(partner.commission_rate)
        send_html_email(
            subject=f"Your Intera IMS affiliate partnership: {partner.code}",
            message=f"Accept your Intera IMS affiliate invitation and finish setting up your account: {invite_url}",
            to_email=[partner.email],
            html_file='emails/affiliate_partner_invitation.html',
            from_email=getattr(settings, 'EMAIL_SYSTEM_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL),
            context={
                'partner_name': partner.name,
                'partner_email': partner.email,
                'referral_code': partner.code,
                'commission_rate': partner.commission_rate,
                'commission_rate_display': commission_rate_display,
                'agreement_terms': agreement_terms,
                'invite_url': invite_url,
                'expires_at': invitation.expires_at,
            },
        )
        response.data['invitation_status'] = invitation.status
        response.data['invitation_expires_at'] = invitation.expires_at.isoformat()
        response.data['account_user'] = str(partner.account_user_id)
        return response

    def perform_update(self, serializer):
        previous = serializer.instance
        previous_values = {
            field: getattr(previous, field)
            for field in ('code', 'commission_rate', 'notes', 'is_active')
        }
        partner = serializer.save()
        if partner.account_user_id:
            sync_affiliate_account_user(partner)
        if any(getattr(partner, field) != value for field, value in previous_values.items()):
            send_affiliate_notification(
                partner,
                subject='Your Intera IMS affiliate link was updated',
                title='Affiliate link updated',
                message='Your affiliate partnership details have been updated by Intera IMS.',
                details=[
                    ('Referral code', partner.code),
                    ('Commission rate', commission_rate_percent(partner.commission_rate)),
                    ('Status', 'Active' if partner.is_active else 'Inactive'),
                    ('Agreement terms', affiliate_agreement_terms(partner.commission_rate)),
                ],
            )


class AffiliatePartnerInvitationLookupView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = str(request.query_params.get('token') or '')
        invitation = AffiliatePartnerInvitation.objects.select_related('partner').filter(
            token_hash=AffiliatePartnerInvitation.hash_token(token),
            status=AffiliatePartnerInvitation.Status.PENDING,
        ).first()
        if not invitation:
            return Response({'detail': 'Invitation is invalid or no longer available.'}, status=status.HTTP_404_NOT_FOUND)
        if invitation.expires_at <= timezone.now():
            invitation.status = AffiliatePartnerInvitation.Status.EXPIRED
            invitation.save(update_fields=['status'])
            return Response({'detail': 'Invitation has expired.'}, status=status.HTTP_410_GONE)
        return Response({
            'email': invitation.email,
            'partner_name': invitation.partner.name,
            'referral_code': invitation.partner.code,
            'expires_at': invitation.expires_at.isoformat(),
        })


class AffiliatePartnerInvitationAcceptView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = str(request.data.get('token') or '').strip()
        first_name = str(request.data.get('first_name') or '').strip()
        last_name = str(request.data.get('last_name') or '').strip()
        password = request.data.get('password')

        with transaction.atomic():
            invitation = AffiliatePartnerInvitation.objects.select_for_update().select_related('partner').filter(
                token_hash=AffiliatePartnerInvitation.hash_token(token),
            ).first()
            if not invitation or invitation.status != AffiliatePartnerInvitation.Status.PENDING:
                return Response({'detail': 'Invitation is invalid or no longer available.'}, status=status.HTTP_400_BAD_REQUEST)
            if invitation.expires_at <= timezone.now():
                invitation.status = AffiliatePartnerInvitation.Status.EXPIRED
                invitation.save(update_fields=['status'])
                return Response({'detail': 'Invitation has expired.'}, status=status.HTTP_410_GONE)
            if not first_name:
                return Response({'detail': 'First name is required.'}, status=status.HTTP_400_BAD_REQUEST)

            partner = invitation.partner
            user = User.objects.select_for_update().filter(email__iexact=invitation.email).first()
            if user is None:
                user = User.objects.create_user(invitation.email, password=None)
            if not user.has_usable_password():
                if not password:
                    return Response({'detail': 'Password is required for a new affiliate account.'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    validate_password(password, user)
                except DjangoValidationError as error:
                    return Response({'password': list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
                user.set_password(password)

            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.is_verified = True
            user.is_affiliate_marketer = True
            user.save(update_fields=[
                'first_name', 'last_name', 'is_active', 'is_verified',
                'is_affiliate_marketer', 'password',
            ])

            sync_affiliate_account_user(partner, user)
            partner.account_user = user
            partner.save(update_fields=['account_user', 'updated_at'])
            invitation.status = AffiliatePartnerInvitation.Status.ACCEPTED
            invitation.accepted_user = user
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['status', 'accepted_user', 'accepted_at'])

        return Response({'detail': 'Affiliate invitation accepted. Sign in to continue.', 'email': user.email}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ReferralPayoutViewSet(viewsets.ModelViewSet):
    """Staff-only manual payout review and release queue."""
    queryset = ReferralPayout.objects.select_related(
        'referrer_user', 'referred_user', 'affiliate_partner'
    ).all()
    serializer_class = ReferralPayoutSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'head', 'options']
    pagination_class = StandardResultsSetPagination
    ordering = ('-created_at',)

    def perform_update(self, serializer):
        # Payment execution remains deliberately manual; this only records the
        # staff decision after the external transfer has been completed.
        previous_status = serializer.instance.status
        payout = serializer.save()
        if previous_status != ReferralPayout.Status.PAID and payout.status == ReferralPayout.Status.PAID and payout.affiliate_partner:
            send_affiliate_notification(
                payout.affiliate_partner,
                subject='Your affiliate payout has been released',
                title='Affiliate payout released',
                message='Your affiliate commission has been marked as paid by Intera IMS.',
                details=[
                    ('Payout amount', f'{payout.payout_amount} {payout.currency}'),
                    ('Payment reference', payout.payment_reference),
                    ('Status', 'Paid'),
                ],
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
            _issue_email_verification_code(
                user,
                subject='Your Verification Code',
                message='Use this code to verify your login: {code}',
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

        if not _consume_email_verification_code(user, code_input):
            return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)
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

    @staticmethod
    def _accepted(value):
        return str(value).strip().lower() in {"1", "true", "yes"}

    def get(self, request, *args, **kwargs):
        """Carry the signup consent decision through the OAuth redirect."""
        requested_intent = request.GET.get("intent")
        if requested_intent is None and request.GET.get("signup") == "1":
            requested_intent = "signup"
        intent = (requested_intent or "login").strip().lower()
        if intent not in {"login", "signup"}:
            return Response(
                {"detail": "Invalid social authentication intent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.session["social_auth_intent"] = intent
        request.session.modified = True

        if intent == "signup":
            if not (
                self._accepted(request.GET.get("terms_accepted"))
                and self._accepted(request.GET.get("privacy_accepted"))
            ):
                request.session.pop("social_auth_intent", None)
                request.session.modified = True
                return Response(
                    {"detail": "Both legal policies must be accepted before social signup."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.session["social_signup_legal_consent"] = {
                "terms_version": TERMS_POLICY_VERSION,
                "privacy_version": PRIVACY_POLICY_VERSION,
            }
            request.session.modified = True

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        social_signup_consent = request.session.get("social_signup_legal_consent")
        try:
            response = super().post(request, *args, **kwargs)

            if response.status_code == 201:
                if social_signup_consent:
                    user_id = response.data.get("id")
                    user = User.objects.filter(id=user_id).first()
                    if user:
                        record_signup_consents(user, request=request, source="social_signup")
                    request.session.pop("social_signup_legal_consent", None)
                    request.session.modified = True
                access_token = response.data.get('access')
                refresh_token = response.data.get('refresh')
                _set_session_cookies(response, access_token=access_token, refresh_token=refresh_token)

            if response.status_code == status.HTTP_400_BAD_REQUEST:
                detail = ""
                if hasattr(response.data, "get"):
                    detail = str(response.data.get("detail", ""))
                    if not detail:
                        non_field_errors = response.data.get("non_field_errors", [])
                        detail = str(non_field_errors[0]) if non_field_errors else ""
                if not detail:
                    detail = str(response.data)
                if "Create an account first" in detail:
                    response.data = {
                        "code": "social_login_requires_signup",
                        "detail": detail,
                    }

            return response
        finally:
            request.session.pop("social_auth_intent", None)
            request.session.modified = True


class NativeProviderAuthTicketView(CustomProviderAuthView):
    """Complete native login in the browser, then hand the app one opaque ticket."""

    ticket_ttl_seconds = 60

    def get(self, request, *args, **kwargs):
        """Start native OAuth in the browser so its session cookie is retained."""
        response = super().get(request, *args, **kwargs)
        authorization_url = response.data.get("authorization_url") if hasattr(response.data, "get") else None
        if response.status_code == status.HTTP_200_OK and authorization_url:
            response.status_code = status.HTTP_302_FOUND
            response["Location"] = authorization_url
            response.data = ""
        return response

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code not in {status.HTTP_200_OK, status.HTTP_201_CREATED}:
            return response

        ticket = secrets.token_urlsafe(48)
        payload = dict(response.data)
        cache.set(f"native-oauth-ticket:{ticket}", payload, self.ticket_ttl_seconds)
        # Native clients receive the session through the ticket exchange, not browser cookies.
        response.delete_cookie(settings.AUTH_COOKIE, path=settings.AUTH_COOKIE_PATH, domain=settings.AUTH_COOKIE_DOMAIN)
        response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_COOKIE_PATH, domain=settings.AUTH_COOKIE_DOMAIN)
        response.data = {"ticket": ticket, "expires_in": self.ticket_ttl_seconds}
        return response


class NativeOAuthTicketExchangeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        ticket = str(request.data.get("ticket") or "").strip()
        if not ticket or len(ticket) < 32:
            return Response({"detail": "Invalid or expired native sign-in ticket."}, status=status.HTTP_400_BAD_REQUEST)
        cache_key = f"native-oauth-ticket:{ticket}"
        payload = cache.get(cache_key)
        if not payload:
            return Response({"detail": "Invalid or expired native sign-in ticket."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(cache_key)
        return Response(payload, status=status.HTTP_200_OK)


class CompanyContextSwitchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        previous_support_grant = _get_request_support_grant(request)
        serializer = CompanyContextSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        platform = serializer.validated_data["platform"]
        profile_access = MyTokenObtainPairSerializer.resolve_active_profile_access(
            request.user,
            profile_id=serializer.validated_data.get("profile_id"),
            company_code=serializer.validated_data.get("company_code"),
            support_access_grant_id=serializer.validated_data.get("support_access_grant_id"),
        )
        profile = profile_access.profile
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
            support_grant=profile_access.support_grant,
            platform=platform,
        )
        payload = _build_auth_payload(
            request.user,
            profile,
            refresh,
            access,
            support_grant=profile_access.support_grant,
            platform=platform,
        )
        previous_support_grant_id = str(previous_support_grant.id) if previous_support_grant else None
        current_support_grant_id = (
            str(profile_access.support_grant.id) if profile_access.support_grant is not None else None
        )
        if previous_support_grant is not None and previous_support_grant_id != current_support_grant_id:
            publish_support_access_workspace_exited(
                previous_support_grant,
                actor=build_actor(request=request, user=request.user),
            )
        if profile_access.support_grant is not None and previous_support_grant_id != current_support_grant_id:
            publish_support_access_workspace_entered(
                profile_access.support_grant,
                actor=build_actor(
                    request=request,
                    user=request.user,
                    role=profile_access.support_grant.membership_role,
                ),
            )
        response = Response(payload, status=status.HTTP_200_OK)
        _set_session_cookies(response, access_token=str(access), refresh_token=str(refresh))
        return response


class CompanyMembershipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profiles = MyTokenObtainPairSerializer.list_accessible_profile_contexts(request.user)
        profile_map = {str(item.profile.id): item for item in profiles}

        active_access = None
        auth = getattr(request, "auth", None)
        token_profile_id = None
        token_support_grant_id = None
        if auth is not None and hasattr(auth, "payload"):
            token_profile_id = auth.payload.get("profile_id")
            token_support_grant_id = auth.payload.get("support_access_grant_id")
        if token_profile_id:
            active_access = profile_map.get(str(token_profile_id))
        if not active_access and request.user.profile_id:
            active_access = profile_map.get(str(request.user.profile_id))
        if token_support_grant_id:
            active_access = MyTokenObtainPairSerializer.resolve_active_profile_access(
                request.user,
                profile_id=token_profile_id if token_profile_id else None,
                support_access_grant_id=token_support_grant_id,
            )

        return Response(
            {
                "active_profile_id": str(active_access.profile.id) if active_access and active_access.profile else None,
                "profiles": [
                    MyTokenObtainPairSerializer._profile_payload(
                        profile.profile,
                        request.user,
                        support_grant=profile.support_grant,
                    )
                    for profile in profiles
                ],
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
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
        support_grant = _get_request_support_grant(request)
        if support_grant is not None:
            publish_support_access_workspace_exited(
                support_grant,
                actor=build_actor(request=request, user=request.user),
            )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_session_cookies(response)
        return response

class MfaSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        force = str(request.data.get('force', '')).strip().lower() in {'1', 'true', 'yes'}

        if user.mfa_enabled and user.has_setup_mfa:
            return Response(
                {"detail": "MFA is already enabled for this account."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if force or not user.mfa_secret:
            user.mfa_secret = pyotp.random_base32()
            user.mfa_enabled = False
            user.has_setup_mfa = False
            user.save(update_fields=['mfa_secret', 'mfa_enabled', 'has_setup_mfa'])

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
        return _build_mfa_verified_response(request, user)


class MfaEmailRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        _issue_email_verification_code(
            user,
            subject='Your Login Verification Code',
            message='Use this code to complete sign in: {code}',
        )
        return Response(
            {
                "detail": "A login verification code has been sent to your email.",
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class MfaEmailVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        code = (request.data.get('code') or '').strip()

        if not code:
            return Response(
                {"detail": "Verification code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not _consume_email_verification_code(user, code):
            return Response(
                {"detail": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return _build_mfa_verified_response(request, user)


class MfaResetRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        _issue_email_verification_code(
            user,
            subject='Your MFA Reset Code',
            message='Use this code to reset your MFA setup: {code}',
        )
        return Response(
            {
                "detail": "A recovery code has been sent to your email.",
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )


class MfaResetConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = get_user_model().objects.get(id=request.user.id)
        code = (request.data.get('code') or '').strip()

        if not code:
            return Response(
                {"detail": "Recovery code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not _consume_email_verification_code(user, code):
            return Response(
                {"detail": "Invalid or expired recovery code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.mfa_secret = None
        user.mfa_enabled = False
        user.has_setup_mfa = False
        user.save(update_fields=['mfa_secret', 'mfa_enabled', 'has_setup_mfa'])

        return Response(
            {
                "detail": "MFA reset confirmed. Set up a new authenticator app to continue.",
                "mfa_enabled": False,
                "has_setup_mfa": False,
            },
            status=status.HTTP_200_OK
        )


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
