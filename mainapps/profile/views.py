import csv
import os
import secrets
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework import filters, status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mainapps.accounts.api.serializers import MyUserSerializer
from mainapps.common.settings import get_company_or_profile
from mainapps.permit.permit import HasModelRequestPermission, PermissionRequiredMixin
from mainapps.permit.models import PlatformChoices
from subapps.kafka.producers import (
    build_actor,
    publish_support_access_grant_activated,
    publish_support_access_grant_created,
    publish_support_access_grant_declined,
    publish_support_access_grant_extended,
    publish_support_access_grant_revoked,
)
from subapps.kafka.producers.platform_events import publish_audit_fact
from subapps.kafka.producers.access_control import (
    _group_names,
    _permission_codes,
    publish_group_changed,
    publish_invitation_changed,
    publish_invitation_notification,
    publish_membership_changed,
    publish_role_assignment_changed,
    publish_role_changed,
    publish_user_groups_updated,
    user_display_name,
)
from subapps.email_system.emails import send_html_email
from subapps.pagination import OptionalPageNumberPagination

from .models import (
    CompanyMembership,
    CompanyInvitation,
    CompanyProfile,
    CompanyProfileAddress,
    InventoryPolicy,
    RecallPolicy,
    ReorderStrategy,
    SupportAccessGrant,
    StaffGroup,
    StaffRole,
    StaffRoleAssignment,
    TrustedWorkspaceDevice,
)
from .default_staff_presets import populate_default_staff_access
from .support_access import expire_support_grants, user_has_direct_profile_access
from .support_access_presets import get_support_access_preset
from .serializers import (
    AddStaffSerializer,
    AssignUserToRoleSerializer,
    CompanyInvitationRespondSerializer,
    CompanyInvitationSerializer,
    CompanyProfileAddressSerializer,
    CompanyProfileDetailSerializer,
    CompanyProfileListSerializer,
    InventoryPolicySerializer,
    RecallPolicySerializer,
    ReorderStrategySerializer,
    CompanyMembershipStaffSerializer,
    StaffAssignmentSerializer,
    StaffGroupListSerializer,
    StaffGroupSerializer,
    StaffRoleAssignmentSerializer,
    StaffRoleListSerializer,
    StaffRoleSerializer,
    TrustedWorkspaceDeviceSerializer,
    SupportAccessGrantCreateSerializer,
    SupportAccessGrantExtendSerializer,
    SupportAccessGrantRespondSerializer,
    SupportAccessGrantRevokeSerializer,
    SupportAccessGrantSerializer,
    serialize_support_access_presets,
)

User = get_user_model()


def _profile_from_request(request):
    auth = getattr(request, "auth", None)
    token_profile_id = None
    support_access_grant_id = None
    if auth is not None and hasattr(auth, "payload"):
        token_profile_id = auth.payload.get("profile_id")
        support_access_grant_id = auth.payload.get("support_access_grant_id")
    if not token_profile_id:
        raise PermissionDenied("No active company context. Switch company before accessing this resource.")
    profile = get_company_or_profile(
        request.user,
        profile_id=token_profile_id,
        support_access_grant_id=support_access_grant_id,
    )
    if not profile:
        raise PermissionDenied("Profile context is not accessible for this user.")
    return profile


def _platform_from_request(request, *, data=None):
    value = data.get("platform") if data is not None else request.query_params.get("platform")
    platform = value or PlatformChoices.INTERA_IMS
    if platform not in PlatformChoices.values:
        raise ValidationError({"platform": "Unknown platform."})
    return platform


def _staff_usage(profile, *, include_pending=True):
    user_ids = set(
        CompanyMembership.objects.filter(profile=profile, is_active=True)
        .values_list("user_id", flat=True)
    )
    if profile.owner_id:
        user_ids.add(profile.owner_id)
    user_ids.update(User.objects.filter(profile=profile).values_list("id", flat=True))

    pending_count = 0
    if include_pending:
        active_emails = {
            email.strip().lower()
            for email in User.objects.filter(id__in=user_ids)
            .exclude(email__isnull=True)
            .values_list("email", flat=True)
            if email
        }
        pending_emails = {
            email.strip().lower()
            for email in CompanyInvitation.objects.filter(
                profile=profile,
                status=CompanyInvitation.InvitationStatus.PENDING,
                expires_at__gt=timezone.now(),
            ).values_list("email", flat=True)
            if email and email.strip().lower() not in active_emails
        }
        pending_count = len(pending_emails)
    return len(user_ids) + pending_count


def _enforce_staff_limit(profile, *, include_pending=True):
    from subapps.services.subscription_entitlements import enforce_subscription_limit

    return enforce_subscription_limit(
        profile_id=profile.id,
        feature="staff-users",
        usage=_staff_usage(profile, include_pending=include_pending),
    )


def _require_subscription_service_key(request):
    expected = os.getenv("SUBSCRIPTION_SERVICE_KEY", "")
    supplied = request.headers.get("X-Intera-Service-Key", "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise PermissionDenied("Invalid subscription service key.")


def _require_hosperator_notification_service_token(request):
    """Authenticate Notification's minimum-necessary group-membership read."""
    expected = os.getenv("HOSPERATOR_NOTIFICATION_SERVICE_TOKEN", "")
    authorization = str(request.headers.get("Authorization", "")).strip()
    scheme, separator, supplied = authorization.partition(" ")
    token = supplied.strip() if separator and scheme.lower() == "bearer" else ""
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise PermissionDenied("Invalid Hosperator notification service token.")


class InternalSubscriptionUsageView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _require_subscription_service_key(request)
        profile_id = request.query_params.get("profile_id")
        profile = CompanyProfile.objects.filter(id=profile_id).first()
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"staff-users": _staff_usage(profile)})


class InternalHosperatorGroupMembersView(APIView):
    """Resolve one active group for Notification without exposing staff details or permissions."""

    authentication_classes = []
    permission_classes = []
    _maximum_members = 200

    def get(self, request, profile_id, group_id):
        _require_hosperator_notification_service_token(request)
        group = (
            StaffGroup.objects.select_related("profile")
            .filter(pk=group_id, profile_id=profile_id, is_active=True)
            .first()
        )
        if group is None:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)

        # Match StaffGroup membership rules: the profile owner or an active profile member only.
        member_user_ids = list(
            group.users.filter(is_active=True)
            .filter(
                Q(pk=group.profile.owner_id)
                | Q(company_memberships__profile_id=profile_id, company_memberships__is_active=True)
            )
            .order_by("pk")
            .values_list("pk", flat=True)
            .distinct()[: self._maximum_members + 1]
        )
        if len(member_user_ids) > self._maximum_members:
            return Response(
                {"detail": "Group exceeds the operational notification membership limit."},
                status=status.HTTP_409_CONFLICT,
            )

        response = Response(
            {
                "profile_id": profile_id,
                "group_id": str(group_id),
                "member_user_ids": [str(user_id) for user_id in member_user_ids],
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class CompanyProfileViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = CompanyProfile.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    required_permission = {
        "list": "read_company",
        "retrieve": "read_company",
        "create": "create_company",
        "update": "update_company",
        "partial_update": "update_company",
        "destroy": "delete_company",
        "staff_active_assignments": "manage_company_settings",
        "add_staff": "manage_company_settings",
        "remove_staff": "manage_company_settings",
        "roles": "manage_company_settings",
        "groups": "manage_company_settings",
        "populate_default_access": "manage_company_settings",
        "addresses": "read_company_address",
        "add_address": "create_company_address",
        "policies": "manage_inventory_settings",
        "analytics": "read_company",
    }

    filterset_fields = ["is_verified", "industry"]
    search_fields = ["name", "description", "tax_id"]
    ordering_fields = ["name", "created_at", "employees_count"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyProfileListSerializer
        return CompanyProfileDetailSerializer

    def perform_create(self, serializer):
        profile = serializer.save(owner=self.request.user)
        CompanyMembership.objects.update_or_create(
            user=self.request.user,
            profile=profile,
            defaults={
                "role": CompanyMembership.MembershipRole.OWNER,
                "is_active": True,
            },
        )
        if not self.request.user.profile_id:
            User.objects.filter(id=self.request.user.id).update(profile=profile)
            self.request.user.profile = profile

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.request.user.is_staff:
            return queryset

        profile = _profile_from_request(self.request)
        return queryset.filter(id=profile.id)

    @action(detail=True, methods=["get"])
    def staff_active_assignments(self, request, pk=None):
        profile = self.get_object()
        staff_memberships = (
            CompanyMembership.objects.filter(
                profile=profile,
                is_active=True,
            )
            .select_related("user", "profile")
        )
        serializer = CompanyMembershipStaffSerializer(staff_memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_staff(self, request, pk=None):
        profile = self.get_object()
        platform = _platform_from_request(request)
        serializer = AddStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = StaffRole.objects.filter(pk=serializer.validated_data["role_id"]).first()
        if role is None or role.platform != platform:
            raise ValidationError({"role_id": "The role must belong to the active platform."})

        assignment = StaffRoleAssignment.objects.create(
            user_id=serializer.validated_data["user_id"],
            role_id=serializer.validated_data["role_id"],
            profile=profile,
            start_date=serializer.validated_data.get("start_date", timezone.now()),
            end_date=serializer.validated_data.get("end_date"),
            assigned_by=request.user,
        )
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=build_actor(request=request, user=request.user),
                assignment=assignment,
                event_name="identity.role_assignment.created",
                summary=f"{assignment.role.name} access was assigned to {user_display_name(assignment.user)}.",
            )
        )
        return Response(
            StaffAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def remove_staff(self, request, pk=None):
        profile = self.get_object()
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response(
                {"error": "User was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        membership = CompanyMembership.objects.filter(
            profile=profile,
            user_id=user_id,
            is_active=True,
        ).first()

        if profile.owner_id == user.id or (membership and membership.role == CompanyMembership.MembershipRole.OWNER):
            return Response(
                {"error": "Owner cannot be removed from the company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignments_qs = StaffRoleAssignment.objects.filter(
            profile=profile,
            user_id=user_id,
            is_active=True,
        )
        assignments = list(assignments_qs.select_related("user", "role", "profile"))
        had_assignments = assignments_qs.exists()

        if membership is None and not had_assignments:
            return Response(
                {"error": "User is not a staff member of this profile"},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        if had_assignments:
            assignments_qs.update(is_active=False, end_date=now)

        if membership:
            membership_before = {
                "role": membership.role,
                "is_active": membership.is_active,
                "permissions": _permission_codes(membership.custom_permissions.all()),
            }
            membership.is_active = False
            membership.save(update_fields=["is_active", "updated_at"])
            transaction.on_commit(
                lambda: publish_membership_changed(
                    actor=build_actor(request=request, user=request.user),
                    membership=membership,
                    event_name="identity.membership.deactivated",
                    summary=f"Workspace membership deactivated for {user_display_name(user)}.",
                    severity="warning",
                    before=membership_before,
                )
            )

        groups = StaffGroup.objects.filter(profile=profile, users__id=user.id)
        before_groups = _group_names(groups)
        for group in groups:
            group.users.remove(user)

        transaction.on_commit(
            lambda: [
                publish_role_assignment_changed(
                    actor=build_actor(request=request, user=request.user),
                    assignment=assignment,
                    event_name="identity.role_assignment.deleted",
                    summary=f"{assignment.role.name} assignment was removed from {user_display_name(assignment.user)}.",
                    severity="warning",
                )
                for assignment in assignments
            ]
        )
        if before_groups:
            transaction.on_commit(
                lambda: publish_user_groups_updated(
                    profile=profile,
                    actor=build_actor(request=request, user=request.user),
                    user=user,
                    before_groups=before_groups,
                    after_groups=[],
                )
            )

        return Response(
            {
                "message": "Staff member removed successfully",
                "deactivated_assignments": assignments_qs.count() if had_assignments else 0,
                "deactivated_membership": bool(membership),
            }
        )

    @action(detail=True, methods=["get"])
    def roles(self, request, pk=None):
        profile = self.get_object()
        platform = _platform_from_request(request)
        serializer = StaffRoleSerializer(profile.get_staff_roles().filter(platform=platform), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def groups(self, request, pk=None):
        profile = self.get_object()
        platform = _platform_from_request(request)
        serializer = StaffGroupSerializer(profile.get_staff_groups().filter(platform=platform), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="populate-default-access")
    def populate_default_access(self, request, pk=None):
        profile = self.get_object()
        platform = _platform_from_request(request)
        payload = populate_default_staff_access(profile, platform=platform)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def addresses(self, request, pk=None):
        profile = self.get_object()
        serializer = CompanyProfileAddressSerializer(profile.addresses.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_address(self, request, pk=None):
        profile = self.get_object()
        serializer = CompanyProfileAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(profile=profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def policies(self, request, pk=None):
        profile = self.get_object()
        payload = {
            "recall_policies": RecallPolicySerializer(
                profile.recall_policies.all(), many=True
            ).data,
            "reorder_strategies": ReorderStrategySerializer(
                profile.reorder_strategies.all(), many=True
            ).data,
            "inventory_policies": InventoryPolicySerializer(
                profile.inventory_policies.all(), many=True
            ).data,
        }
        return Response(payload)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        profile = self.get_object()
        total_staff = CompanyMembership.objects.filter(
            profile=profile,
            is_active=True,
        ).count()
        active_roles = profile.get_staff_roles().filter(is_active=True).count()
        active_groups = profile.get_staff_groups().filter(is_active=True).count()
        total_policies = (
            profile.recall_policies.count()
            + profile.reorder_strategies.count()
            + profile.inventory_policies.count()
        )
        analytics = {
            "total_staff": total_staff,
            "active_roles": active_roles,
            "active_groups": active_groups,
            "total_addresses": profile.addresses.count(),
            "total_policies": total_policies,
            "verification_status": profile.is_verified,
            "profile_age_days": (timezone.now().date() - profile.created_at.date()).days,
        }
        return Response(analytics)

class CompanyInvitationViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by")
    serializer_class = CompanyInvitationSerializer
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "destroy": "manage_company_settings",
        "invite": "manage_company_settings",
        "invite_bulk": "manage_company_settings",
        "pending": "manage_company_settings",
        "resend": "manage_company_settings",
        "revoke": "manage_company_settings",
    }
    filterset_fields = ["status", "role", "email"]
    search_fields = ["email", "profile__name", "invitation_code"]
    ordering_fields = ["created_at", "updated_at", "expires_at"]
    ordering = ["-created_at"]

    @staticmethod
    def _expire_stale_pending(queryset):
        now = timezone.now()
        stale = queryset.filter(
            status=CompanyInvitation.InvitationStatus.PENDING,
            expires_at__lte=now,
        )
        stale.update(
            status=CompanyInvitation.InvitationStatus.EXPIRED,
            responded_at=now,
            updated_at=now,
        )

    def get_permissions(self):
        if self.action in {"accept", "decline", "mine"}:
            return [IsAuthenticated()]
        if self.action == "resolve":
            return []
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.action == "mine":
            queryset = queryset.filter(
                email__iexact=self.request.user.email,
            )
            self._expire_stale_pending(queryset)
            return queryset

        if self.request.user.is_staff:
            self._expire_stale_pending(queryset)
            return queryset

        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        queryset = queryset.filter(profile=profile)
        self._expire_stale_pending(queryset)
        return queryset

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        role = serializer.validated_data.get("role", CompanyMembership.MembershipRole.MEMBER)
        if role == CompanyMembership.MembershipRole.OWNER:
            raise PermissionDenied("Owner invitations are not allowed.")
        _enforce_staff_limit(profile)
        serializer.save(profile=profile, invited_by=self.request.user)

    @staticmethod
    def _normalize_email(value):
        email = (value or "").strip().lower()
        if not email:
            return None
        try:
            validate_email(email)
        except ValidationError:
            return None
        return email

    @staticmethod
    def _build_invitation_accept_url(invitation):
        template = getattr(settings, "COMPANY_INVITATION_ACCEPT_URL_TEMPLATE", "").strip()
        frontend_url = getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
        if not template:
            if not frontend_url:
                return ""
            return f"{frontend_url}/accounts/invitations/{quote(invitation.invitation_code, safe='')}"
        try:
            return template.format(code=invitation.invitation_code)
        except (IndexError, KeyError, ValueError):
            return template

    def _send_invitation_email(self, request, invitation):
        inviter_email = invitation.invited_by.email if invitation.invited_by_id else "an administrator"
        subject = f"Invitation to join {invitation.profile.name}"
        message = (
            invitation.invitation_message.strip()
            or f"{inviter_email} invited you to join {invitation.profile.name}."
        )
        send_html_email(
            subject=subject,
            message=message,
            to_email=[invitation.email],
            html_file="emails/company_invitation.html",
            from_email=getattr(settings, "EMAIL_ACCOUNTS_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            context={
                "company_name": invitation.profile.name,
                "invited_by_email": inviter_email,
                "invitation_code": invitation.invitation_code,
                "invitation_message": invitation.invitation_message.strip(),
                "role_label": invitation.get_role_display(),
                "expires_at": invitation.expires_at,
                "accept_url": self._build_invitation_accept_url(invitation),
                "recipient_email": invitation.email,
            },
        )

    def _publish_invitation_notification(self, request, invitation, *, event_name: str, title: str, message: str):
        accept_url = self._build_invitation_accept_url(invitation)
        transaction.on_commit(
            lambda: publish_invitation_notification(
                invitation=invitation,
                actor=build_actor(request=request, user=request.user),
                event_name=event_name,
                title=title,
                message=message,
                action_url=accept_url,
            )
        )

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        profile = _profile_from_request(request)
        if not profile:
            return Response(
                {"detail": "No company profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        role = serializer.validated_data.get("role", CompanyMembership.MembershipRole.MEMBER)
        invitation_message = serializer.validated_data.get("invitation_message", "")

        if role == CompanyMembership.MembershipRole.OWNER:
            return Response(
                {"detail": "Owner invitations are not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_membership = CompanyMembership.objects.filter(
            profile=profile,
            user__email__iexact=email,
            is_active=True,
        ).exists()
        if existing_membership:
            return Response(
                {"detail": "This email already belongs to the company."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_pending = CompanyInvitation.objects.filter(
            profile=profile,
            email__iexact=email,
            status=CompanyInvitation.InvitationStatus.PENDING,
        ).first()
        if existing_pending and existing_pending.expires_at > timezone.now():
            self._send_invitation_email(request, existing_pending)
            self._publish_invitation_notification(
                request,
                existing_pending,
                event_name="notification.identity.invitation.resent",
                title="Workspace invitation resent",
                message=f"Your invitation to join {existing_pending.profile.name} was resent.",
            )
            publish_invitation_changed(
                actor=build_actor(request=request, user=request.user),
                invitation=existing_pending,
                event_name="identity.invitation.resent",
                summary=f"Workspace invitation resent to {existing_pending.email}.",
            )
            return Response(self.get_serializer(existing_pending).data, status=status.HTTP_200_OK)

        _enforce_staff_limit(profile)
        expires_days = getattr(settings, "COMPANY_INVITATION_EXPIRY_DAYS", 2)
        invitation = CompanyInvitation.objects.create(
            profile=profile,
            email=email,
            role=role,
            invited_by=request.user,
            invitation_message=invitation_message,
            expires_at=timezone.now() + timedelta(days=expires_days),
        )
        self._send_invitation_email(request, invitation)
        self._publish_invitation_notification(
            request,
            invitation,
            event_name="notification.identity.invitation.sent",
            title="Workspace invitation received",
            message=f"You were invited to join {invitation.profile.name}.",
        )
        publish_invitation_changed(
            actor=build_actor(request=request, user=request.user),
            invitation=invitation,
            event_name="identity.invitation.created",
            summary=f"Workspace invitation created for {invitation.email}.",
        )
        return Response(self.get_serializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="invite-bulk")
    def invite_bulk(self, request):
        profile = _profile_from_request(request)
        if not profile:
            return Response(
                {"detail": "No company profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = request.data.get("role") or CompanyMembership.MembershipRole.MEMBER
        allowed_roles = {choice[0] for choice in CompanyMembership.MembershipRole.choices}
        if role not in allowed_roles:
            return Response(
                {"detail": "Invalid role. Allowed roles are: member, admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role == CompanyMembership.MembershipRole.OWNER:
            return Response(
                {"detail": "Owner invitations are not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation_message = request.data.get("invitation_message", "")
        raw_emails = request.data.get("emails", [])
        if isinstance(raw_emails, str):
            raw_emails = [item.strip() for item in raw_emails.split(",")]
        elif not isinstance(raw_emails, list):
            raw_emails = []

        upload = request.FILES.get("file") or request.FILES.get("csv_file")
        if upload:
            decoded_content = upload.read().decode("utf-8-sig")
            reader = csv.reader(StringIO(decoded_content))
            rows = list(reader)
            if rows:
                header = [cell.strip().lower() for cell in rows[0]]
                has_header = "email" in header
                email_index = header.index("email") if has_header else 0
                data_rows = rows[1:] if has_header else rows
                for row in data_rows:
                    if not row:
                        continue
                    if email_index >= len(row):
                        continue
                    raw_emails.append(row[email_index].strip())

        if not raw_emails:
            return Response(
                {"detail": "Provide at least one email via `emails` or a CSV file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        expires_days = getattr(settings, "COMPANY_INVITATION_EXPIRY_DAYS", 2)
        seen = set()
        created_invites = []
        existing_pending = []
        skipped = []
        invalid = []

        for raw in raw_emails:
            email = self._normalize_email(raw)
            if not email:
                if raw:
                    invalid.append(raw)
                continue
            if email in seen:
                continue
            seen.add(email)

            if CompanyMembership.objects.filter(
                profile=profile,
                user__email__iexact=email,
                is_active=True,
            ).exists():
                skipped.append({"email": email, "reason": "already_member"})
                continue

            existing = CompanyInvitation.objects.filter(
                profile=profile,
                email__iexact=email,
                status=CompanyInvitation.InvitationStatus.PENDING,
            ).first()
            if existing and existing.expires_at > now:
                existing_pending.append(existing)
                self._send_invitation_email(request, existing)
                self._publish_invitation_notification(
                    request,
                    existing,
                    event_name="notification.identity.invitation.resent",
                    title="Workspace invitation resent",
                    message=f"Your invitation to join {existing.profile.name} was resent.",
                )
                publish_invitation_changed(
                    actor=build_actor(request=request, user=request.user),
                    invitation=existing,
                    event_name="identity.invitation.resent",
                    summary=f"Workspace invitation resent to {existing.email}.",
                )
                continue

            try:
                _enforce_staff_limit(profile)
            except PermissionDenied:
                skipped.append({"email": email, "reason": "subscription_limit_reached"})
                continue
            invitation = CompanyInvitation.objects.create(
                profile=profile,
                email=email,
                role=role,
                invited_by=request.user,
                invitation_message=invitation_message,
                expires_at=now + timedelta(days=expires_days),
            )
            created_invites.append(invitation)
            self._send_invitation_email(request, invitation)
            self._publish_invitation_notification(
                request,
                invitation,
                event_name="notification.identity.invitation.sent",
                title="Workspace invitation received",
                message=f"You were invited to join {invitation.profile.name}.",
            )
            publish_invitation_changed(
                actor=build_actor(request=request, user=request.user),
                invitation=invitation,
                event_name="identity.invitation.created",
                summary=f"Workspace invitation created for {invitation.email}.",
            )

        return Response(
            {
                "created_count": len(created_invites),
                "existing_pending_count": len(existing_pending),
                "skipped_count": len(skipped),
                "invalid_count": len(invalid),
                "created": self.get_serializer(created_invites, many=True).data,
                "existing_pending": self.get_serializer(existing_pending, many=True).data,
                "skipped": skipped,
                "invalid_emails": invalid,
            },
            status=status.HTTP_201_CREATED if created_invites else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request):
        profile = _profile_from_request(request)
        if not profile:
            return Response([], status=status.HTTP_200_OK)
        invitations = self.get_queryset().filter(
            profile=profile,
            status=CompanyInvitation.InvitationStatus.PENDING,
        )
        return Response(self.get_serializer(invitations, many=True).data)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        invitations = self.get_queryset().filter(
            email__iexact=request.user.email,
            status=CompanyInvitation.InvitationStatus.PENDING,
        )
        return Response(self.get_serializer(invitations, many=True).data)

    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request):
        code = (request.query_params.get("invitation_code") or request.query_params.get("code") or "").strip()
        if not code:
            return Response({"detail": "invitation_code is required"}, status=status.HTTP_400_BAD_REQUEST)

        invitation = CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by").filter(
            invitation_code=code
        ).first()
        if not invitation:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        payload = self.get_serializer(invitation).data
        payload["is_registered_user"] = User.objects.filter(email__iexact=invitation.email, is_active=True).exists()
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="resend")
    def resend(self, request, pk=None):
        invitation = self.get_object()
        profile = _profile_from_request(request)
        if not profile or profile.id != invitation.profile_id:
            raise PermissionDenied("Invitation does not belong to your active profile.")
        before = {
            "status": invitation.status,
            "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else "",
        }
        expires_days = getattr(settings, "COMPANY_INVITATION_EXPIRY_DAYS", 2)
        invitation.status = CompanyInvitation.InvitationStatus.PENDING
        invitation.expires_at = timezone.now() + timedelta(days=expires_days)
        invitation.save(update_fields=["status", "expires_at", "updated_at"])
        self._send_invitation_email(request, invitation)
        self._publish_invitation_notification(
            request,
            invitation,
            event_name="notification.identity.invitation.resent",
            title="Workspace invitation resent",
            message=f"Your invitation to join {invitation.profile.name} was resent.",
        )
        publish_invitation_changed(
            actor=build_actor(request=request, user=request.user),
            invitation=invitation,
            event_name="identity.invitation.resent",
            summary=f"Workspace invitation resent to {invitation.email}.",
            before=before,
        )
        return Response(self.get_serializer(invitation).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        profile = _profile_from_request(request)
        if not profile or profile.id != invitation.profile_id:
            raise PermissionDenied("Invitation does not belong to your active profile.")
        before = {
            "status": invitation.status,
            "responded_at": invitation.responded_at.isoformat() if invitation.responded_at else "",
        }
        invitation.status = CompanyInvitation.InvitationStatus.REVOKED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at", "updated_at"])
        transaction.on_commit(
            lambda: publish_invitation_changed(
                actor=build_actor(request=request, user=request.user),
                invitation=invitation,
                event_name="identity.invitation.revoked",
                summary=f"Workspace invitation revoked for {invitation.email}.",
                severity="warning",
                before=before,
            )
        )
        return Response(self.get_serializer(invitation).data)

    @action(detail=False, methods=["post"], url_path="accept")
    def accept(self, request):
        serializer = CompanyInvitationRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invitation_code"].strip()
        invitation = CompanyInvitation.objects.filter(invitation_code=code).first()
        if not invitation:
            return Response(
                {"detail": "Invalid invitation code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.email.strip().lower() != invitation.email.strip().lower():
            return Response(
                {"detail": "Authenticated user email does not match invitation email."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.status != CompanyInvitation.InvitationStatus.PENDING:
            return Response(
                {"detail": "Invitation is not pending."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.expires_at and invitation.expires_at < timezone.now():
            invitation.status = CompanyInvitation.InvitationStatus.EXPIRED
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=["status", "responded_at", "updated_at"])
            return Response(
                {"detail": "Invitation has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _enforce_staff_limit(invitation.profile, include_pending=False)

        membership, created = CompanyMembership.objects.get_or_create(
            user=request.user,
            profile=invitation.profile,
            defaults={
                "role": invitation.role,
                "is_active": True,
                "invited_by": invitation.invited_by,
            },
        )
        membership_before = {
            "role": membership.role,
            "is_active": membership.is_active,
            "permissions": _permission_codes(membership.custom_permissions.all()),
        }
        if not created:
            membership.role = invitation.role
            membership.is_active = True
            if invitation.invited_by and not membership.invited_by_id:
                membership.invited_by = invitation.invited_by
            membership.save(update_fields=["role", "is_active", "invited_by", "updated_at"])

        invitation_before = {
            "status": invitation.status,
            "accepted_by_user_id": str(invitation.accepted_by_id or ""),
        }
        invitation.status = CompanyInvitation.InvitationStatus.ACCEPTED
        invitation.accepted_by = request.user
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])

        if not request.user.profile_id:
            request.user.profile = invitation.profile
            request.user.save(update_fields=["profile"])

        publish_invitation_changed(
            actor=build_actor(request=request, user=request.user),
            invitation=invitation,
            event_name="identity.invitation.accepted",
            summary=f"Workspace invitation accepted by {request.user.email}.",
            before=invitation_before,
        )
        transaction.on_commit(
            lambda: publish_membership_changed(
                actor=build_actor(request=request, user=request.user),
                membership=membership,
                event_name="identity.membership.activated" if created or not membership_before["is_active"] else "identity.membership.updated",
                summary=f"Workspace membership activated for {user_display_name(request.user)}.",
                before=membership_before,
            )
        )

        return Response(
            {
                "membership_id": str(membership.id),
                "profile_id": str(invitation.profile_id),
                "role": membership.role,
                "status": invitation.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="decline")
    def decline(self, request):
        serializer = CompanyInvitationRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invitation_code"].strip()
        invitation = CompanyInvitation.objects.filter(invitation_code=code).first()
        if not invitation:
            return Response(
                {"detail": "Invalid invitation code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.email.strip().lower() != invitation.email.strip().lower():
            return Response(
                {"detail": "Authenticated user email does not match invitation email."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.status != CompanyInvitation.InvitationStatus.PENDING:
            return Response(
                {"detail": "Invitation is not pending."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = {
            "status": invitation.status,
            "accepted_by_user_id": str(invitation.accepted_by_id or ""),
        }
        invitation.status = CompanyInvitation.InvitationStatus.DECLINED
        invitation.responded_at = timezone.now()
        invitation.accepted_by = request.user
        invitation.save(update_fields=["status", "responded_at", "accepted_by", "updated_at"])
        publish_invitation_changed(
            actor=build_actor(request=request, user=request.user),
            invitation=invitation,
            event_name="identity.invitation.declined",
            summary=f"Workspace invitation declined by {request.user.email}.",
            severity="warning",
            before=before,
        )
        return Response({"detail": "Invitation declined."}, status=status.HTTP_200_OK)


class SupportAccessGrantViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = SupportAccessGrant.objects.select_related(
        "profile",
        "grantee_user",
        "created_by",
        "approved_by",
        "revoked_by",
    ).prefetch_related("custom_permissions")
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "read_support_access_grant",
        "retrieve": "read_support_access_grant",
        "create": "create_support_access_grant",
        "extend": "update_support_access_grant",
        "revoke": "revoke_support_access_grant",
        "presets": "read_support_access_grant",
        "support_users": "create_support_access_grant",
        "mine": "read_support_access_grant",
    }
    filterset_fields = ["permission_mode", "membership_role", "status", "ticket_reference"]
    search_fields = ["grantee_email_snapshot", "reason", "ticket_reference", "grantee_user__email"]
    ordering_fields = ["created_at", "starts_at", "expires_at", "updated_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in {"mine", "accept", "decline"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.action == "mine":
            expire_support_grants(user=self.request.user)
            return queryset.filter(
                grantee_email_snapshot__iexact=self.request.user.email,
                status=SupportAccessGrant.Status.PENDING,
            ).order_by(*self.ordering)

        profile = _profile_from_request(self.request)
        expire_support_grants(profile=profile)
        return queryset.filter(profile=profile).order_by(*self.ordering)

    def get_serializer_class(self):
        if self.action == "create":
            return SupportAccessGrantCreateSerializer
        return SupportAccessGrantSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            return context
        if self.action not in {"mine", "accept", "decline"}:
            context["profile"] = _profile_from_request(self.request)
        return context

    @staticmethod
    def _merge_notes(existing_notes, new_note, *, actor_email):
        note = (new_note or "").strip()
        if not note:
            return existing_notes
        stamped_note = f"[{timezone.now().isoformat()}] {actor_email}: {note}"
        if not existing_notes:
            return stamped_note
        return f"{existing_notes}\n{stamped_note}"

    def create(self, request, *args, **kwargs):
        from subapps.services.subscription_entitlements import enforce_subscription_limit

        profile = _profile_from_request(request)
        enforce_subscription_limit(
            profile_id=profile.id,
            feature="support-access",
            usage=0,
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = serializer.save()
        self._send_support_access_request_email(grant)
        publish_support_access_grant_created(grant, actor=build_actor(request=request, user=request.user))
        return Response(
            SupportAccessGrantSerializer(grant, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _build_support_access_accept_url(grant):
        template = getattr(settings, "SUPPORT_ACCESS_ACCEPT_URL_TEMPLATE", "").strip()
        frontend_url = getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
        if not template:
            if not frontend_url:
                return ""
            return f"{frontend_url}/accounts/support-access/{quote(grant.invitation_code, safe='')}"
        try:
            return template.format(code=grant.invitation_code)
        except (IndexError, KeyError, ValueError):
            return template

    def _send_support_access_request_email(self, grant):
        requester_email = grant.created_by.email if grant.created_by_id else "a workspace administrator"
        preset = get_support_access_preset(grant.permission_mode)
        send_html_email(
            subject=f"Temporary support access request for {grant.profile.name}",
            message=grant.reason.strip() or f"{requester_email} requested temporary access for {grant.profile.name}.",
            to_email=[grant.grantee_email_snapshot],
            html_file="emails/support_access_request.html",
            from_email=getattr(settings, "EMAIL_ACCOUNTS_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            context={
                "company_name": grant.profile.name,
                "requester_email": requester_email,
                "recipient_email": grant.grantee_email_snapshot,
                "reason": grant.reason.strip(),
                "ticket_reference": grant.ticket_reference,
                "preset_name": preset.name if preset else grant.permission_mode,
                "permission_mode": grant.permission_mode,
                "membership_role": grant.get_membership_role_display(),
                "starts_at": grant.starts_at,
                "expires_at": grant.expires_at,
                "accept_url": self._build_support_access_accept_url(grant),
                "invitation_code": grant.invitation_code,
                "is_registered_user": bool(grant.grantee_user_id),
            },
        )

    @action(detail=False, methods=["get"], url_path="presets")
    def presets(self, request):
        return Response(serialize_support_access_presets(), status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        grants = self.get_queryset()
        return Response(SupportAccessGrantSerializer(grants, many=True).data)

    @action(detail=False, methods=["get"], url_path="support-users")
    def support_users(self, request):
        query = (request.query_params.get("q") or "").strip()
        profile = _profile_from_request(request)
        if len(query) < 2:
            return Response([], status=status.HTTP_200_OK)

        users = (
            User.objects.filter(is_active=True)
            .filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .exclude(
                Q(id=profile.owner_id)
                | Q(company_memberships__profile=profile, company_memberships__is_active=True)
            )
            .distinct()
            .order_by("email")[:20]
        )
        return Response(MyUserSerializer(users, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        grant = self.get_object()
        serializer = SupportAccessGrantRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if grant.current_status == SupportAccessGrant.Status.REVOKED:
            return Response(
                SupportAccessGrantSerializer(grant, context=self.get_serializer_context()).data,
                status=status.HTTP_200_OK,
            )

        grant.notes = self._merge_notes(
            grant.notes,
            serializer.validated_data.get("notes"),
            actor_email=request.user.email,
        )
        grant.revoke(revoked_by=request.user)
        if "notes" in serializer.validated_data and serializer.validated_data.get("notes", "").strip():
            grant.save(update_fields=["notes", "updated_at"])
        publish_support_access_grant_revoked(grant, actor=build_actor(request=request, user=request.user))

        return Response(SupportAccessGrantSerializer(grant, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["post"], url_path="accept")
    def accept(self, request):
        serializer = SupportAccessGrantRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invitation_code"].strip()
        grant = SupportAccessGrant.objects.filter(invitation_code=code).first()
        if not grant:
            return Response({"detail": "Invalid support access request code."}, status=status.HTTP_400_BAD_REQUEST)

        request_email = request.user.email.strip().lower()
        if request_email != grant.grantee_email_snapshot.strip().lower():
            return Response(
                {"detail": "Authenticated user email does not match the support access request email."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if grant.grantee_user_id and grant.grantee_user_id != request.user.id:
            return Response(
                {"detail": "Support access request is reserved for a different account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if grant.current_status != SupportAccessGrant.Status.PENDING:
            return Response({"detail": "Support access request is not pending."}, status=status.HTTP_400_BAD_REQUEST)
        if grant.expires_at and grant.expires_at < timezone.now():
            grant.status = SupportAccessGrant.Status.EXPIRED
            grant.responded_at = timezone.now()
            grant.save(update_fields=["status", "responded_at", "updated_at"])
            return Response({"detail": "Support access request has expired."}, status=status.HTTP_400_BAD_REQUEST)
        if user_has_direct_profile_access(request.user, grant.profile):
            return Response(
                {"detail": "This account already has direct access to the workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grant.grantee_user = request.user
        grant.accepted_by = request.user
        grant.responded_at = timezone.now()
        grant.save()
        publish_support_access_grant_activated(
            grant,
            actor=build_actor(request=request, user=request.user, role=grant.membership_role),
        )
        return Response(
            {
                "support_access_grant_id": str(grant.id),
                "profile_id": str(grant.profile_id),
                "status": grant.current_status,
                "starts_at": grant.starts_at.isoformat() if grant.starts_at else None,
                "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="decline")
    def decline(self, request):
        serializer = SupportAccessGrantRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invitation_code"].strip()
        grant = SupportAccessGrant.objects.filter(invitation_code=code).first()
        if not grant:
            return Response({"detail": "Invalid support access request code."}, status=status.HTTP_400_BAD_REQUEST)

        request_email = request.user.email.strip().lower()
        if request_email != grant.grantee_email_snapshot.strip().lower():
            return Response(
                {"detail": "Authenticated user email does not match the support access request email."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if grant.grantee_user_id and grant.grantee_user_id != request.user.id:
            return Response(
                {"detail": "Support access request is reserved for a different account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if grant.current_status != SupportAccessGrant.Status.PENDING:
            return Response({"detail": "Support access request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        grant.accepted_by = request.user
        grant.responded_at = timezone.now()
        grant.status = SupportAccessGrant.Status.DECLINED
        grant.save(update_fields=["accepted_by", "responded_at", "status", "updated_at"])
        publish_support_access_grant_declined(
            grant,
            actor=build_actor(request=request, user=request.user, role=grant.membership_role),
        )
        return Response({"detail": "Support access request declined."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="extend")
    def extend(self, request, pk=None):
        grant = self.get_object()
        serializer = SupportAccessGrantExtendSerializer(data=request.data, context={"grant": grant})
        serializer.is_valid(raise_exception=True)

        grant.expires_at = serializer.validated_data["expires_at"]
        grant.notes = self._merge_notes(
            grant.notes,
            serializer.validated_data.get("notes"),
            actor_email=request.user.email,
        )
        if grant.approved_by_id is None:
            grant.approved_by = request.user
        grant.save()
        publish_support_access_grant_extended(grant, actor=build_actor(request=request, user=request.user))
        return Response(SupportAccessGrantSerializer(grant, context=self.get_serializer_context()).data)


class TrustedWorkspaceDeviceViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    """Manage revocable workspace device trust without touching POS terminals."""

    queryset = TrustedWorkspaceDevice.objects.select_related("profile", "created_by", "revoked_by")
    serializer_class = TrustedWorkspaceDeviceSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["platform", "is_active", "is_revoked"]
    search_fields = ["device_identifier", "device_label"]
    ordering_fields = ["device_identifier", "device_label", "created_at", "last_seen_at"]
    ordering = ["device_label", "device_identifier"]
    http_method_names = ["get", "post", "head", "options"]
    required_permission = {
        "list": "hosperator.device_binding.manage",
        "retrieve": "hosperator.device_binding.manage",
        "create": "hosperator.device_binding.manage",
        "revoke": "hosperator.device_binding.manage",
    }

    def get_permissions(self):
        # A staff member may read only the binding for the current device. The
        # ability to bind or revoke devices remains separately permissioned.
        if getattr(self, "action", None) == "current":
            return [IsAuthenticated()]
        return super().get_permissions()

    def _platform(self):
        value = self.request.query_params.get("platform") or PlatformChoices.HOSPERATOR
        if value not in PlatformChoices.values:
            raise ValidationError({"platform": "Unknown platform."})
        return value

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        return queryset.filter(profile=profile, platform=self._platform())

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        device = serializer.save(
            profile=profile,
            created_by=self.request.user,
        )
        transaction.on_commit(
            lambda: publish_audit_fact(
                event_name="identity.trusted_workspace_device.created",
                payload={
                    "profile_id": str(profile.id),
                    "device_id": device.device_identifier,
                    "binding_id": str(device.id),
                    "platform": device.platform,
                    "capabilities": device.capabilities,
                },
                workspace_id=str(profile.id),
                actor=build_actor(request=self.request, user=self.request.user),
                target={"type": "trusted_workspace_device", "id": str(device.id), "label": device.device_label or device.device_identifier},
                summary=f"Trusted device {device.device_label or device.device_identifier} was bound.",
                key=f"{profile.id}:{device.id}",
            )
        )

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        device_id = str(request.headers.get("X-Device-ID", "")).strip()
        if not device_id:
            return Response({"detail": "X-Device-ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        profile = _profile_from_request(request)
        binding = self.get_queryset().filter(device_identifier=device_id, is_active=True, is_revoked=False).first()
        if binding is None:
            return Response(
                {
                    "is_enrolled": False,
                    "device_id": device_id,
                    "profile_id": str(profile.id),
                    "platform": self._platform(),
                    "binding": None,
                },
                status=status.HTTP_200_OK,
            )
        binding.last_seen_at = timezone.now()
        binding.save(update_fields=["last_seen_at", "updated_at"])
        return Response(
            {
                "is_enrolled": True,
                "device_id": device_id,
                "profile_id": str(profile.id),
                "platform": binding.platform,
                "binding": self.get_serializer(binding).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        binding = self.get_object()
        if binding.is_revoked:
            return Response(self.get_serializer(binding).data, status=status.HTTP_200_OK)
        binding.revoke(revoked_by=request.user)
        transaction.on_commit(
            lambda: publish_audit_fact(
                event_name="identity.trusted_workspace_device.revoked",
                payload={
                    "profile_id": str(binding.profile_id),
                    "device_id": binding.device_identifier,
                    "binding_id": str(binding.id),
                    "platform": binding.platform,
                },
                workspace_id=str(binding.profile_id),
                actor=build_actor(request=request, user=request.user),
                target={"type": "trusted_workspace_device", "id": str(binding.id), "label": binding.device_label or binding.device_identifier},
                summary=f"Trusted device {binding.device_label or binding.device_identifier} was revoked.",
                severity="warning",
                key=f"{binding.profile_id}:{binding.id}",
            )
        )
        return Response(self.get_serializer(binding).data, status=status.HTTP_200_OK)


class StaffRoleViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "update": "manage_company_settings",
        "partial_update": "manage_company_settings",
        "destroy": "manage_company_settings",
    }

    filterset_fields = ["is_active", "profile", "platform"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return StaffRoleListSerializer
        return StaffRoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        platform = _platform_from_request(self.request)
        return queryset.filter(
            Q(profile=profile) | Q(is_system=True, profile__isnull=True),
            platform=platform,
        )

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        platform = _platform_from_request(self.request, data=serializer.validated_data)
        if StaffRole.objects.filter(
            platform=platform,
            name__iexact=serializer.validated_data["name"],
            is_system=True,
        ).exists():
            raise ValidationError("That name is reserved for a system role on this platform.")
        role = serializer.save(
            profile=profile,
            platform=platform,
            created_by=self.request.user,
            is_system=False,
        )
        transaction.on_commit(
            lambda: publish_role_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                role=role,
                event_name="identity.role.created",
                summary=f"Role {role.name} was created.",
            )
        )

    def perform_update(self, serializer):
        role = self.get_object()
        if role.is_system:
            raise PermissionDenied("System roles are managed by Intera staff and cannot be edited.")
        before = {
            "role_name": role.name,
            "description": role.description or "",
            "is_active": role.is_active,
        }
        updated_role = serializer.save()
        after = {
            "role_name": updated_role.name,
            "description": updated_role.description or "",
            "is_active": updated_role.is_active,
        }
        transaction.on_commit(
            lambda: publish_role_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                role=updated_role,
                event_name="identity.role.updated",
                summary=f"Role {updated_role.name} was updated.",
                before=before,
                after=after,
            )
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System roles are managed by Intera staff and cannot be deleted.")
        actor = build_actor(request=self.request, user=self.request.user)
        transaction.on_commit(
            lambda: publish_role_changed(
                actor=actor,
                role=instance,
                event_name="identity.role.deleted",
                summary=f"Role {instance.name} was deleted.",
                severity="warning",
                before={
                    "role_name": instance.name,
                    "description": instance.description or "",
                    "is_active": instance.is_active,
                },
                after={},
            )
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        role = self.get_object()
        assignments = role.assignments.filter(is_active=True)
        serializer = StaffAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign_user(self, request, pk=None):
        role = self.get_object()
        active_profile = _profile_from_request(request)
        serializer = AssignUserToRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment = StaffRoleAssignment.objects.create(
            user_id=serializer.validated_data["user_id"],
            role=role,
            profile=active_profile,
            start_date=serializer.validated_data.get("start_date", timezone.now()),
            end_date=serializer.validated_data.get("end_date"),
            assigned_by=request.user,
        )
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=build_actor(request=request, user=request.user),
                assignment=assignment,
                event_name="identity.role_assignment.created",
                summary=f"{assignment.role.name} access was assigned to {user_display_name(assignment.user)}.",
            )
        )
        return Response(
            StaffAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class StaffRoleAssignmentViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRoleAssignment.objects.all()
    serializer_class = StaffRoleAssignmentSerializer
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active", "role", "user", "role__platform"]
    ordering_fields = ["start_date", "end_date", "assigned_at"]
    ordering = ["-assigned_at"]
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "update": "manage_company_settings",
        "partial_update": "manage_company_settings",
        "destroy": "manage_company_settings",
        "deactivate": "manage_company_settings",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if profile:
            platform = _platform_from_request(self.request)
            return queryset.filter(profile=profile, role__platform=platform)
        return queryset.none()

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")

        requested_profile = serializer.validated_data.get("profile")
        if requested_profile and requested_profile.id != profile.id:
            raise PermissionDenied("Cross-profile assignment is not allowed.")

        role = serializer.validated_data["role"]
        platform = _platform_from_request(self.request)
        if role.platform != platform:
            raise ValidationError({"role": "The role must belong to the active platform."})
        if role.profile_id not in (None, profile.id) or (role.is_system and role.profile_id is not None):
            raise PermissionDenied("Cross-profile role assignment is not allowed.")
        assignment = serializer.save(profile=profile, assigned_by=self.request.user)
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                assignment=assignment,
                event_name="identity.role_assignment.created",
                summary=f"{assignment.role.name} access was assigned to {user_display_name(assignment.user)}.",
            )
        )

    def perform_update(self, serializer):
        platform = _platform_from_request(self.request)
        assignment = self.get_object()
        requested_role = serializer.validated_data.get("role", assignment.role)
        if requested_role.platform != platform:
            raise ValidationError({"role": "The role must belong to the active platform."})
        assignment = serializer.save()
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                assignment=assignment,
                event_name="identity.role_assignment.updated",
                summary=f"{assignment.role.name} assignment was updated for {user_display_name(assignment.user)}.",
            )
        )

    def perform_destroy(self, instance):
        actor = build_actor(request=self.request, user=self.request.user)
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=actor,
                assignment=instance,
                event_name="identity.role_assignment.deleted",
                summary=f"{instance.role.name} assignment was removed from {user_display_name(instance.user)}.",
                severity="warning",
            )
        )
        instance.delete()

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        assignment = self.get_object()
        assignment.is_active = False
        assignment.end_date = timezone.now()
        assignment.save(update_fields=["is_active", "end_date"])
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=build_actor(request=request, user=request.user),
                assignment=assignment,
                event_name="identity.role_assignment.deactivated",
                summary=f"{assignment.role.name} assignment was deactivated for {user_display_name(assignment.user)}.",
                severity="warning",
            )
        )
        return Response({"detail": "Role assignment deactivated successfully"})


class StaffGroupViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffGroup.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    pagination_class = OptionalPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "update": "manage_company_settings",
        "partial_update": "manage_company_settings",
        "destroy": "manage_company_settings",
    }

    filterset_fields = ["is_active", "profile", "platform"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return StaffGroupListSerializer
        return StaffGroupSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        platform = _platform_from_request(self.request)
        return queryset.filter(
            Q(profile=profile) | Q(is_system=True, profile__isnull=True),
            platform=platform,
        )

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        platform = _platform_from_request(self.request, data=serializer.validated_data)
        if StaffGroup.objects.filter(
            platform=platform,
            name__iexact=serializer.validated_data["name"],
            is_system=True,
        ).exists():
            raise ValidationError("That name is reserved for a system group on this platform.")
        group = serializer.save(
            profile=profile,
            platform=platform,
            created_by=self.request.user,
            is_system=False,
        )
        transaction.on_commit(
            lambda: publish_group_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                group=group,
                event_name="identity.group.created",
                summary=f"Group {group.name} was created.",
            )
        )

    def perform_update(self, serializer):
        group = self.get_object()
        if group.is_system:
            raise PermissionDenied("System groups are managed by Intera staff and cannot be edited.")
        before = {
            "group_name": group.name,
            "description": group.description or "",
            "is_active": group.is_active,
        }
        updated_group = serializer.save()
        after = {
            "group_name": updated_group.name,
            "description": updated_group.description or "",
            "is_active": updated_group.is_active,
        }
        transaction.on_commit(
            lambda: publish_group_changed(
                actor=build_actor(request=self.request, user=self.request.user),
                group=updated_group,
                event_name="identity.group.updated",
                summary=f"Group {updated_group.name} was updated.",
                before=before,
                after=after,
            )
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System groups are managed by Intera staff and cannot be deleted.")
        actor = build_actor(request=self.request, user=self.request.user)
        transaction.on_commit(
            lambda: publish_group_changed(
                actor=actor,
                group=instance,
                event_name="identity.group.deleted",
                summary=f"Group {instance.name} was deleted.",
                severity="warning",
                before={
                    "group_name": instance.name,
                    "description": instance.description or "",
                    "is_active": instance.is_active,
                },
                after={},
            )
        )
        instance.delete()

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        group = self.get_object()
        serializer = MyUserSerializer(group.users.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_user(self, request, pk=None):
        group = self.get_object()
        active_profile = _profile_from_request(request)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(id=user_id).first()
        is_member = (
            user
            and (
                active_profile.owner_id == user.id
                or CompanyMembership.objects.filter(
                    user=user,
                    profile=active_profile,
                    is_active=True,
                ).exists()
            )
        )
        if not is_member:
            return Response(
                {"error": "User does not belong to this profile"},
                status=status.HTTP_404_NOT_FOUND,
            )
        before_groups = _group_names(
            user.staff_groups.filter(
                Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
                platform=group.platform,
            )
        )
        group.users.add(user)
        after_groups = _group_names(
            user.staff_groups.filter(
                Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
                platform=group.platform,
            )
        )
        transaction.on_commit(
            lambda: publish_user_groups_updated(
                profile=active_profile,
                actor=build_actor(request=request, user=request.user),
                user=user,
                before_groups=before_groups,
                after_groups=after_groups,
            )
        )
        return Response({"message": "User added to group successfully"})

    @action(detail=True, methods=["post"])
    def remove_user(self, request, pk=None):
        group = self.get_object()
        active_profile = _profile_from_request(request)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(id=user_id).first()
        is_member = (
            user
            and (
                active_profile.owner_id == user.id
                or CompanyMembership.objects.filter(
                    user=user,
                    profile=active_profile,
                    is_active=True,
                ).exists()
            )
        )
        if not is_member:
            return Response(
                {"error": "User does not belong to this profile"},
                status=status.HTTP_404_NOT_FOUND,
            )
        before_groups = _group_names(
            user.staff_groups.filter(
                Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
                platform=group.platform,
            )
        )
        group.users.remove(user)
        after_groups = _group_names(
            user.staff_groups.filter(
                Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
                platform=group.platform,
            )
        )
        transaction.on_commit(
            lambda: publish_user_groups_updated(
                profile=active_profile,
                actor=build_actor(request=request, user=request.user),
                user=user,
                before_groups=before_groups,
                after_groups=after_groups,
            )
        )
        return Response({"message": "User removed from group successfully"})


class CompanyProfileAddressViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = CompanyProfileAddress.objects.all()
    serializer_class = CompanyProfileAddressSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "read_company_address",
        "retrieve": "read_company_address",
        "create": "create_company_address",
        "update": "update_company_address",
        "partial_update": "update_company_address",
        "destroy": "delete_company_address",
    }

    filterset_fields = ["address_type", "profile"]
    search_fields = ["street", "city__name", "region__name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")

        serializer.save(profile=profile)
        address = serializer.instance
        if not profile.headquarters_address:
            profile.headquarters_address = address
            profile.save(update_fields=["headquarters_address"])


class RecallPolicyViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = RecallPolicy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_inventory_settings",
        "retrieve": "manage_inventory_settings",
        "create": "manage_inventory_settings",
        "update": "manage_inventory_settings",
        "partial_update": "manage_inventory_settings",
        "destroy": "manage_inventory_settings",
    }

    filterset_fields = ["is_active", "profile"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]
    serializer_class = RecallPolicySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        serializer.save(profile=profile, created_by=self.request.user)


class ReorderStrategyViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = ReorderStrategy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_inventory_settings",
        "retrieve": "manage_inventory_settings",
        "create": "manage_inventory_settings",
        "update": "manage_inventory_settings",
        "partial_update": "manage_inventory_settings",
        "destroy": "manage_inventory_settings",
    }

    filterset_fields = ["is_active", "profile", "strategy_type", "applies_to_all"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at"]
    serializer_class = ReorderStrategySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        serializer.save(profile=profile, created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        category_id = request.query_params.get("category_id")
        if not category_id:
            return Response(
                {"error": "category_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        strategies = self.get_queryset().filter(
            Q(applies_to_all=True) | Q(applies_to_categories__icontains=category_id)
        )
        serializer = self.get_serializer(strategies, many=True)
        return Response(serializer.data)


class InventoryPolicyViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = InventoryPolicy.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_inventory_settings",
        "retrieve": "manage_inventory_settings",
        "create": "manage_inventory_settings",
        "update": "manage_inventory_settings",
        "partial_update": "manage_inventory_settings",
        "destroy": "manage_inventory_settings",
    }

    filterset_fields = ["is_active", "profile", "policy_type", "applies_to_all"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "effective_date"]
    ordering = ["-created_at"]
    serializer_class = InventoryPolicySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        profile = _profile_from_request(self.request)
        if profile:
            queryset = queryset.filter(profile=profile)
        else:
            queryset = queryset.none()

        active_only = self.request.query_params.get("active_only")
        if active_only and active_only.lower() == "true":
            today = timezone.now().date()
            queryset = queryset.filter(
                is_active=True,
                effective_date__lte=today,
            ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        return queryset

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        serializer.save(profile=profile, created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        category_id = request.query_params.get("category_id")
        if not category_id:
            return Response(
                {"error": "category_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        policies = self.get_queryset().filter(
            Q(applies_to_all=True) | Q(applies_to_categories__icontains=category_id)
        )
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        today = timezone.now().date()
        policies = self.get_queryset().filter(
            is_active=True,
            effective_date__lte=today,
        ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)
