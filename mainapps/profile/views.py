import csv
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mainapps.accounts.api.serializers import MyUserSerializer
from mainapps.common.settings import get_company_or_profile
from mainapps.permit.permit import HasModelRequestPermission, PermissionRequiredMixin
from subapps.email_system.emails import send_html_email

from .models import (
    CompanyMembership,
    CompanyInvitation,
    CompanyProfile,
    CompanyProfileAddress,
    ModelVersion,
    ProfileAgent,
    InventoryPolicy,
    RecallPolicy,
    ReorderStrategy,
    StaffGroup,
    StaffRole,
    StaffRoleAssignment,
)
from .serializers import (
    AddStaffSerializer,
    AssignUserToRoleSerializer,
    CompanyInvitationRespondSerializer,
    CompanyInvitationSerializer,
    CompanyProfileAddressSerializer,
    CompanyProfileDetailSerializer,
    CompanyProfileListSerializer,
    InventoryPolicySerializer,
    ModelVersionOptionSerializer,
    ProfileAgentSetupSerializer,
    RecallPolicySerializer,
    ReorderStrategySerializer,
    StaffAssignmentSerializer,
    StaffGroupListSerializer,
    StaffGroupSerializer,
    StaffRoleAssignmentSerializer,
    StaffRoleListSerializer,
    StaffRoleSerializer,
)

User = get_user_model()


def _profile_from_request(request):
    auth = getattr(request, "auth", None)
    token_profile_id = None
    if auth is not None and hasattr(auth, "payload"):
        token_profile_id = auth.payload.get("profile_id")
    if not token_profile_id:
        raise PermissionDenied("No active company context. Switch company before accessing this resource.")
    profile = get_company_or_profile(request.user, profile_id=token_profile_id)
    if not profile:
        raise PermissionDenied("Profile context is not accessible for this user.")
    return profile


class CompanyProfileViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = CompanyProfile.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
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
        if self.request.user.is_staff:
            return queryset

        profile = _profile_from_request(self.request)
        return queryset.filter(id=profile.id)

    @action(detail=True, methods=["get"])
    def staff_active_assignments(self, request, pk=None):
        profile = self.get_object()
        staff_assignments = (
            StaffRoleAssignment.objects.filter(
                profile=profile,
                is_active=True,
                start_date__lte=timezone.now(),
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=timezone.now()))
            .select_related("user", "role")
        )
        serializer = StaffAssignmentSerializer(staff_assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_staff(self, request, pk=None):
        profile = self.get_object()
        serializer = AddStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment = StaffRoleAssignment.objects.create(
            user_id=serializer.validated_data["user_id"],
            role_id=serializer.validated_data["role_id"],
            profile=profile,
            start_date=serializer.validated_data.get("start_date", timezone.now()),
            end_date=serializer.validated_data.get("end_date"),
            assigned_by=request.user,
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
            membership.is_active = False
            membership.save(update_fields=["is_active", "updated_at"])

        groups = StaffGroup.objects.filter(profile=profile, users__id=user.id)
        for group in groups:
            group.users.remove(user)

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
        serializer = StaffRoleSerializer(profile.get_staff_roles(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def groups(self, request, pk=None):
        profile = self.get_object()
        serializer = StaffGroupSerializer(profile.get_staff_groups(), many=True)
        return Response(serializer.data)

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
        total_staff = StaffRoleAssignment.objects.filter(
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


class ProfileAgentSetupView(PermissionRequiredMixin, APIView):
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = "manage_company_settings"

    @staticmethod
    def _available_model_versions():
        return ModelVersion.objects.select_related("llm").order_by("llm__provider", "model_name")

    def get(self, request):
        profile = _profile_from_request(request)
        agent = (
            ProfileAgent.objects.select_related("version", "version__llm")
            .filter(profile=profile)
            .first()
        )
        payload = {
            "configured": bool(agent),
            "agent": ProfileAgentSetupSerializer(agent).data if agent else None,
            "available_versions": ModelVersionOptionSerializer(self._available_model_versions(), many=True).data,
        }
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request):
        profile = _profile_from_request(request)
        instance = (
            ProfileAgent.objects.select_related("version", "version__llm")
            .filter(profile=profile)
            .first()
        )
        serializer = ProfileAgentSetupSerializer(
            instance=instance,
            data=request.data,
            partial=bool(instance),
        )
        serializer.is_valid(raise_exception=True)
        agent = serializer.save(profile=profile)

        response_status = status.HTTP_200_OK if instance else status.HTTP_201_CREATED
        return Response(
            {
                "configured": True,
                "agent": ProfileAgentSetupSerializer(agent).data,
                "available_versions": ModelVersionOptionSerializer(
                    self._available_model_versions(),
                    many=True,
                ).data,
            },
            status=response_status,
        )

    def patch(self, request):
        profile = _profile_from_request(request)
        instance = (
            ProfileAgent.objects.select_related("version", "version__llm")
            .filter(profile=profile)
            .first()
        )
        if not instance:
            return Response(
                {"detail": "Agent setup has not been created for this company profile."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProfileAgentSetupSerializer(instance=instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save(profile=profile)

        return Response(
            {
                "configured": True,
                "agent": ProfileAgentSetupSerializer(agent).data,
                "available_versions": ModelVersionOptionSerializer(
                    self._available_model_versions(),
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class CompanyInvitationViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = CompanyInvitation.objects.select_related("profile", "invited_by", "accepted_by")
    serializer_class = CompanyInvitationSerializer
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

    def get_permissions(self):
        if self.action in {"accept", "decline", "mine"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "mine":
            return queryset.filter(
                email__iexact=self.request.user.email,
                status=CompanyInvitation.InvitationStatus.PENDING,
            )

        if self.request.user.is_staff:
            return queryset

        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        role = serializer.validated_data.get("role", CompanyMembership.MembershipRole.MEMBER)
        if role == CompanyMembership.MembershipRole.OWNER:
            raise PermissionDenied("Owner invitations are not allowed.")
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
        if not template:
            frontend_site_url = getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
            if not frontend_site_url:
                return ""
            return f"{frontend_site_url}/accounts/invitations/{quote(invitation.invitation_code, safe='')}"
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
            return Response(self.get_serializer(existing_pending).data, status=status.HTTP_200_OK)

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

    @action(detail=True, methods=["post"], url_path="resend")
    def resend(self, request, pk=None):
        invitation = self.get_object()
        profile = _profile_from_request(request)
        if not profile or profile.id != invitation.profile_id:
            raise PermissionDenied("Invitation does not belong to your active profile.")
        expires_days = getattr(settings, "COMPANY_INVITATION_EXPIRY_DAYS", 2)
        invitation.status = CompanyInvitation.InvitationStatus.PENDING
        invitation.expires_at = timezone.now() + timedelta(days=expires_days)
        invitation.save(update_fields=["status", "expires_at", "updated_at"])
        self._send_invitation_email(request, invitation)
        return Response(self.get_serializer(invitation).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        profile = _profile_from_request(request)
        if not profile or profile.id != invitation.profile_id:
            raise PermissionDenied("Invitation does not belong to your active profile.")
        invitation.status = CompanyInvitation.InvitationStatus.REVOKED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at", "updated_at"])
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

        membership, created = CompanyMembership.objects.get_or_create(
            user=request.user,
            profile=invitation.profile,
            defaults={
                "role": invitation.role,
                "is_active": True,
                "invited_by": invitation.invited_by,
            },
        )
        if not created:
            membership.role = invitation.role
            membership.is_active = True
            if invitation.invited_by and not membership.invited_by_id:
                membership.invited_by = invitation.invited_by
            membership.save(update_fields=["role", "is_active", "invited_by", "updated_at"])

        invitation.status = CompanyInvitation.InvitationStatus.ACCEPTED
        invitation.accepted_by = request.user
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])

        if not request.user.profile_id:
            request.user.profile = invitation.profile
            request.user.save(update_fields=["profile"])

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

        invitation.status = CompanyInvitation.InvitationStatus.DECLINED
        invitation.responded_at = timezone.now()
        invitation.accepted_by = request.user
        invitation.save(update_fields=["status", "responded_at", "accepted_by", "updated_at"])
        return Response({"detail": "Invitation declined."}, status=status.HTTP_200_OK)


class StaffRoleViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "update": "manage_company_settings",
        "partial_update": "manage_company_settings",
        "destroy": "manage_company_settings",
    }

    filterset_fields = ["is_active", "profile"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return StaffRoleListSerializer
        return StaffRoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        serializer.save(profile=profile, created_by=self.request.user)

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        role = self.get_object()
        assignments = role.assignments.filter(is_active=True)
        serializer = StaffAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign_user(self, request, pk=None):
        role = self.get_object()
        serializer = AssignUserToRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assignment = StaffRoleAssignment.objects.create(
            user_id=serializer.validated_data["user_id"],
            role=role,
            profile=role.profile,
            start_date=serializer.validated_data.get("start_date", timezone.now()),
            end_date=serializer.validated_data.get("end_date"),
            assigned_by=request.user,
        )
        return Response(
            StaffAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class StaffRoleAssignmentViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRoleAssignment.objects.all()
    serializer_class = StaffRoleAssignmentSerializer
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
        profile = _profile_from_request(self.request)
        if profile:
            return queryset.filter(profile=profile)
        return queryset.none()

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")

        requested_profile = serializer.validated_data.get("profile")
        if requested_profile and requested_profile.id != profile.id:
            raise PermissionDenied("Cross-profile assignment is not allowed.")

        serializer.save(profile=profile, assigned_by=self.request.user)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        assignment = self.get_object()
        assignment.is_active = False
        assignment.end_date = timezone.now()
        assignment.save(update_fields=["is_active", "end_date"])
        return Response({"detail": "Role assignment deactivated successfully"})


class StaffGroupViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffGroup.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_company_settings",
        "retrieve": "manage_company_settings",
        "create": "manage_company_settings",
        "update": "manage_company_settings",
        "partial_update": "manage_company_settings",
        "destroy": "manage_company_settings",
    }

    filterset_fields = ["is_active", "profile"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "list":
            return StaffGroupListSerializer
        return StaffGroupSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        profile = _profile_from_request(self.request)
        if not profile:
            return queryset.none()
        return queryset.filter(profile=profile)

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        if not profile:
            raise PermissionDenied("No company profile is linked to this account.")
        serializer.save(profile=profile, created_by=self.request.user)

    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        group = self.get_object()
        serializer = MyUserSerializer(group.users.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_user(self, request, pk=None):
        group = self.get_object()
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
                group.profile.owner_id == user.id
                or CompanyMembership.objects.filter(
                    user=user,
                    profile=group.profile,
                    is_active=True,
                ).exists()
            )
        )
        if not is_member:
            return Response(
                {"error": "User does not belong to this profile"},
                status=status.HTTP_404_NOT_FOUND,
            )
        group.users.add(user)
        return Response({"message": "User added to group successfully"})

    @action(detail=True, methods=["post"])
    def remove_user(self, request, pk=None):
        group = self.get_object()
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
                group.profile.owner_id == user.id
                or CompanyMembership.objects.filter(
                    user=user,
                    profile=group.profile,
                    is_active=True,
                ).exists()
            )
        )
        if not is_member:
            return Response(
                {"error": "User does not belong to this profile"},
                status=status.HTTP_404_NOT_FOUND,
            )
        group.users.remove(user)
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
