from django.db import transaction
from django.db.models import Exists, OuterRef
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from mainapps.accounts.models import User
from mainapps.common.settings import get_company_or_profile
from mainapps.permit.models import CustomUserPermission
from mainapps.permit.permit import HasModelRequestPermission, PermissionRequiredMixin
from mainapps.profile.models import StaffGroup, StaffRole, StaffRoleAssignment

from .serializers import (
    GroupDetailSerializer,
    GroupPermissionUpdateSerializer,
    PermissionDetailSerializer,
    RoleAssignmentSerializer,
    RolePermissionUpdateSerializer,
    UserGroupUpdateSerializer,
    UserPermissionUpdateSerializer,
)


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


def _ensure_same_profile(instance_profile, active_profile):
    if instance_profile != active_profile:
        raise PermissionDenied("You do not have access to this resource.")


def _validated_permissions(codenames):
    valid_permissions = CustomUserPermission.objects.filter(codename__in=codenames)
    received = set(codenames)
    valid_codenames = set(valid_permissions.values_list("codename", flat=True))
    invalid = received - valid_codenames
    if invalid:
        raise ValidationError({"detail": f"Invalid permissions: {', '.join(sorted(invalid))}"})
    return valid_permissions


class RoleAssignmentViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRoleAssignment.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = RoleAssignmentSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(profile=active_profile)


class UserAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = UserPermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(profile=active_profile)

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        user = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(user.profile, active_profile)

        if request.method.lower() == "get":
            permissions_qs = CustomUserPermission.objects.annotate(
                has_permission=Exists(
                    User.custom_permissions.through.objects.filter(
                        user_id=user.id,
                        customuserpermission_id=OuterRef("id"),
                    )
                )
            ).select_related("category")
            serializer = PermissionDetailSerializer(permissions_qs, many=True)
            return Response({"permissions": serializer.data})

        serializer = UserPermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"])
        with transaction.atomic():
            user.custom_permissions.set(valid_permissions)
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "put"], url_path="groups")
    def groups(self, request, pk=None):
        user = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(user.profile, active_profile)

        if request.method.lower() == "get":
            groups_qs = StaffGroup.objects.filter(profile=active_profile).annotate(
                belongs_to=Exists(
                    User.staff_groups.through.objects.filter(
                        user_id=user.id,
                        staffgroup_id=OuterRef("id"),
                    )
                )
            )
            serializer = GroupDetailSerializer(groups_qs, many=True)
            return Response({"groups": serializer.data})

        serializer = UserGroupUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group_ids = serializer.validated_data["groups"]
        valid_groups = StaffGroup.objects.filter(id__in=group_ids, profile=active_profile)
        with transaction.atomic():
            user.staff_groups.set(valid_groups)
        return Response({"status": "groups updated"}, status=status.HTTP_200_OK)


class GroupAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffGroup.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = GroupPermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(profile=active_profile)

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        group = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(group.profile, active_profile)

        if request.method.lower() == "get":
            permissions_qs = CustomUserPermission.objects.annotate(
                has_permission=Exists(
                    StaffGroup.permissions.through.objects.filter(
                        staffgroup_id=group.id,
                        customuserpermission_id=OuterRef("id"),
                    )
                )
            ).select_related("category")
            serializer = PermissionDetailSerializer(permissions_qs, many=True)
            return Response({"permissions": serializer.data})

        serializer = GroupPermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"])
        with transaction.atomic():
            group.permissions.set(valid_permissions)
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)


class RoleAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = RolePermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(profile=active_profile)

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        role = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(role.profile, active_profile)

        if request.method.lower() == "get":
            permissions_qs = CustomUserPermission.objects.annotate(
                has_permission=Exists(
                    StaffRole.permissions.through.objects.filter(
                        staffrole_id=role.id,
                        customuserpermission_id=OuterRef("id"),
                    )
                )
            ).select_related("category")
            serializer = PermissionDetailSerializer(permissions_qs, many=True)
            return Response({"permissions": serializer.data})

        serializer = RolePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"])
        with transaction.atomic():
            role.permissions.set(valid_permissions)
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)


# Backward-compatible aliases for legacy imports.
RoleAssignmentManager = RoleAssignmentViewSet
UserPermissionManager = UserAccessViewSet
GroupPermissionManager = GroupAccessViewSet
RolePermissionManager = RoleAccessViewSet
UserGroupManager = UserAccessViewSet
