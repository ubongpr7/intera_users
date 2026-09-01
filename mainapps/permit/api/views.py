from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from mainapps.accounts.models import User
from mainapps.common.settings import get_company_or_profile
from mainapps.permit.models import CustomUserPermission, PlatformChoices
from mainapps.permit.permit import HasModelRequestPermission, PermissionRequiredMixin
from mainapps.profile.models import CompanyMembership, StaffGroup, StaffRole, StaffRoleAssignment
from subapps.kafka.producers.access_control import (
    _group_names,
    _permission_codes,
    publish_group_permissions_updated,
    publish_role_assignment_changed,
    publish_role_permissions_updated,
    user_display_name,
    publish_user_groups_updated,
    publish_user_permissions_updated,
)
from subapps.kafka.producers.support_access import build_actor

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


def _ensure_same_profile(instance_profile, active_profile):
    if instance_profile is not None and instance_profile != active_profile:
        raise PermissionDenied("You do not have access to this resource.")


def _user_has_profile_access(user: User, active_profile) -> bool:
    if getattr(user, "profile_id", None) == getattr(active_profile, "id", None):
        return True
    return user.company_memberships.filter(profile=active_profile, is_active=True).exists()


def _platform_from_request(request, *, data=None):
    value = data.get("platform") if data is not None else request.query_params.get("platform")
    platform = value or PlatformChoices.INTERA_IMS
    if platform not in PlatformChoices.values:
        raise ValidationError({"platform": "Unknown platform."})
    return platform


def _validated_permissions(codenames, platform):
    valid_permissions = CustomUserPermission.objects.filter(
        codename__in=codenames,
        platform=platform,
    )
    received = set(codenames)
    valid_codenames = set(valid_permissions.values_list("codename", flat=True))
    invalid = received - valid_codenames
    if invalid:
        raise ValidationError({"detail": f"Invalid {platform} permissions: {', '.join(sorted(invalid))}"})
    return valid_permissions


class RoleAssignmentViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRoleAssignment.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = RoleAssignmentSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        membership_user_ids = CompanyMembership.objects.filter(
            profile=active_profile,
            is_active=True,
        ).values_list("user_id", flat=True)
        return (
            super()
            .get_queryset()
            .filter(
                Q(profile=active_profile)
                | Q(user_id__in=membership_user_ids)
            )
            .distinct()
        )

    def perform_create(self, serializer):
        active_profile = _profile_from_request(self.request)
        role = serializer.validated_data["role"]
        user = serializer.validated_data["user"]
        _ensure_same_profile(role.profile, active_profile)
        if not _user_has_profile_access(user, active_profile):
            raise PermissionDenied("The assigned user must belong to the active profile.")
        assignment = serializer.save(profile=active_profile, assigned_by=self.request.user)
        actor = build_actor(request=self.request, user=self.request.user)
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=actor,
                assignment=assignment,
                event_name="identity.role_assignment.created",
                summary=f"{assignment.role.name} access was assigned to {user_display_name(assignment.user)}.",
            )
        )

    def perform_update(self, serializer):
        assignment = serializer.save()
        actor = build_actor(request=self.request, user=self.request.user)
        transaction.on_commit(
            lambda: publish_role_assignment_changed(
                actor=actor,
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


class UserAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = UserPermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return (
            super()
            .get_queryset()
            .filter(
                Q(profile=active_profile)
                | Q(company_memberships__profile=active_profile, company_memberships__is_active=True)
            )
            .distinct()
        )

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        user = self.get_object()
        active_profile = _profile_from_request(request)
        if not _user_has_profile_access(user, active_profile):
            raise PermissionDenied("You do not have access to this resource.")

        if request.method.lower() == "get":
            platform = _platform_from_request(request)
            permissions_qs = CustomUserPermission.objects.filter(platform=platform).annotate(
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
        platform = _platform_from_request(request, data=serializer.validated_data)
        before_permissions = _permission_codes(user.custom_permissions.filter(platform=platform))
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"], platform)
        after_permissions = _permission_codes(valid_permissions)
        with transaction.atomic():
            preserved_permissions = user.custom_permissions.exclude(platform=platform)
            user.custom_permissions.set(preserved_permissions | valid_permissions)
            transaction.on_commit(
                lambda: publish_user_permissions_updated(
                    profile=active_profile,
                    actor=build_actor(request=request, user=request.user),
                    user=user,
                    before_permissions=before_permissions,
                    after_permissions=after_permissions,
                )
            )
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "put"], url_path="groups")
    def groups(self, request, pk=None):
        user = self.get_object()
        active_profile = _profile_from_request(request)
        if not _user_has_profile_access(user, active_profile):
            raise PermissionDenied("You do not have access to this resource.")

        if request.method.lower() == "get":
            platform = _platform_from_request(request)
            groups_qs = StaffGroup.objects.filter(
                Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
                platform=platform,
            ).annotate(
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
        platform = _platform_from_request(request, data=serializer.validated_data)
        before_groups = _group_names(
            user.staff_groups.filter(Q(profile=active_profile) | Q(is_system=True, profile__isnull=True), platform=platform)
        )
        group_ids = serializer.validated_data["groups"]
        valid_groups = StaffGroup.objects.filter(
            Q(profile=active_profile) | Q(is_system=True, profile__isnull=True),
            id__in=group_ids,
            platform=platform,
        )
        if valid_groups.count() != len(set(group_ids)):
            raise ValidationError({"groups": "Every group must belong to the active profile and platform."})
        after_groups = _group_names(valid_groups)
        with transaction.atomic():
            user.staff_groups.remove(
                *user.staff_groups.filter(Q(profile=active_profile) | Q(is_system=True, profile__isnull=True), platform=platform)
            )
            user.staff_groups.add(*valid_groups)
            transaction.on_commit(
                lambda: publish_user_groups_updated(
                    profile=active_profile,
                    actor=build_actor(request=request, user=request.user),
                    user=user,
                    before_groups=before_groups,
                    after_groups=after_groups,
                )
            )
        return Response({"status": "groups updated"}, status=status.HTTP_200_OK)


class GroupAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffGroup.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = GroupPermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(Q(profile=active_profile) | Q(is_system=True, profile__isnull=True))

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        group = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(group.profile, active_profile)
        if group.is_system and request.method.lower() == "put" and not request.user.is_staff:
            raise PermissionDenied("System groups are managed by Intera staff and cannot change permissions.")

        if request.method.lower() == "get":
            platform = _platform_from_request(request)
            if group.platform != platform:
                raise ValidationError({"platform": "The requested platform does not match this group."})
            permissions_qs = CustomUserPermission.objects.filter(platform=platform).annotate(
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
        platform = _platform_from_request(request, data=serializer.validated_data)
        if group.platform != platform:
            raise ValidationError({"platform": "The requested platform does not match this group."})
        before_permissions = _permission_codes(group.permissions.filter(platform=platform))
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"], platform)
        after_permissions = _permission_codes(valid_permissions)
        with transaction.atomic():
            group.permissions.set(valid_permissions)
            transaction.on_commit(
                lambda: publish_group_permissions_updated(
                    actor=build_actor(request=request, user=request.user),
                    group=group,
                    before_permissions=before_permissions,
                    after_permissions=after_permissions,
                )
            )
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)


class RoleAccessViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = StaffRole.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]
    serializer_class = RolePermissionUpdateSerializer
    required_permission = "manage_company_settings"

    def get_queryset(self):
        active_profile = _profile_from_request(self.request)
        return super().get_queryset().filter(Q(profile=active_profile) | Q(is_system=True, profile__isnull=True))

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        role = self.get_object()
        active_profile = _profile_from_request(request)
        _ensure_same_profile(role.profile, active_profile)
        if role.is_system and request.method.lower() == "put" and not request.user.is_staff:
            raise PermissionDenied("System roles are managed by Intera staff and cannot change permissions.")

        if request.method.lower() == "get":
            platform = _platform_from_request(request)
            if role.platform != platform:
                raise ValidationError({"platform": "The requested platform does not match this role."})
            permissions_qs = CustomUserPermission.objects.filter(platform=platform).annotate(
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
        platform = _platform_from_request(request, data=serializer.validated_data)
        if role.platform != platform:
            raise ValidationError({"platform": "The requested platform does not match this role."})
        before_permissions = _permission_codes(role.permissions.filter(platform=platform))
        valid_permissions = _validated_permissions(serializer.validated_data["permissions"], platform)
        after_permissions = _permission_codes(valid_permissions)
        with transaction.atomic():
            role.permissions.set(valid_permissions)
            transaction.on_commit(
                lambda: publish_role_permissions_updated(
                    actor=build_actor(request=request, user=request.user),
                    role=role,
                    before_permissions=before_permissions,
                    after_permissions=after_permissions,
                )
            )
        return Response({"status": "permissions updated"}, status=status.HTTP_200_OK)


# Backward-compatible aliases for legacy imports.
RoleAssignmentManager = RoleAssignmentViewSet
UserPermissionManager = UserAccessViewSet
GroupPermissionManager = GroupAccessViewSet
RolePermissionManager = RoleAccessViewSet
UserGroupManager = UserAccessViewSet
