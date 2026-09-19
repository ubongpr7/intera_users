from rest_framework import permissions

from mainapps.accounts.authorization_context import evaluate_permission_grants
from mainapps.common.settings import get_company_or_profile
from mainapps.permit.models import PlatformChoices
from mainapps.profile.support_access import validate_support_token

class HasModelRequestPermission(permissions.BasePermission):
    """
    Resolve management permissions from the Users source of record.

    Detailed permission and wildcard claims are intentionally not read from the
    access JWT or authorization context. Those claims can be stale and make the
    token grow with every workspace assignment.
    """
    @staticmethod
    def _resolve_required_permission(permission, request):
        """Map shared management APIs to the active product's access permission."""
        if permission != "manage_company_settings":
            return permission
        token = getattr(request, "auth", None)
        payload = getattr(token, "payload", {}) if token is not None else {}
        if payload.get("platform") == "hosperator":
            return "hosperator.staff_access.manage"
        return permission

    def has_permission(self, request, view):
        permission = getattr(view, 'required_permission', None)
        if not permission:
            return False

        if isinstance(permission, dict):
            action = getattr(view, "action", None)
            permission = permission.get(action)
            if not permission:
                return False

        permission = self._resolve_required_permission(permission, request)

        if permission == "create_company":
            profile_id = getattr(request.user, "profile_id", None)
            memberships = getattr(request.user, "company_memberships", None)
            has_memberships = bool(memberships.exists()) if memberships is not None and hasattr(memberships, "exists") else False
            if not profile_id and not has_memberships:
                return True

        # Internal staff manage platform-owned definitions independently of a tenant role.
        if getattr(request.user, "is_superuser", False) or getattr(request.user, "is_staff", False):
            return True

        token = getattr(request, "auth", None)
        payload = getattr(token, "payload", {}) if token is not None else {}
        if not isinstance(payload, dict):
            payload = {}
        profile_id = payload.get("profile_id") or getattr(request.user, "profile_id", None)
        support_access_grant_id = payload.get("support_access_grant_id")
        if not validate_support_token(
            request.user,
            profile_id=profile_id,
            support_access_grant_id=support_access_grant_id,
        ):
            return False

        profile = get_company_or_profile(
            request.user,
            profile_id=profile_id,
            support_access_grant_id=support_access_grant_id,
        )
        if not profile:
            return False
        if profile.owner_id == request.user.id and not support_access_grant_id:
            return True
        platform = payload.get("platform") or PlatformChoices.INTERA_IMS
        if platform not in PlatformChoices.values:
            return False
        support_grant = None
        if support_access_grant_id:
            from mainapps.profile.support_access import get_active_support_grant

            support_grant = get_active_support_grant(
                request.user,
                profile=profile,
                grant_id=support_access_grant_id,
            )
            if not support_grant:
                return False
        grants = evaluate_permission_grants(
            request.user,
            profile=profile,
            support_grant=support_grant,
            platform=platform,
            permissions=[permission],
        )
        return bool(grants.get(permission))
        
class PermissionRequiredMixin:
    """
    Mixin to add permission checking to views
    """
    required_permission = None
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]

    
