from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)

from rest_framework_simplejwt.tokens import UntypedToken
from mainapps.accounts.authorization_context import authorization_context_from_request
from mainapps.profile.support_access import validate_support_token

class HasModelRequestPermission(permissions.BasePermission):
    """
    Microservice-adapted permission class that checks permissions via user service
    """
    def get_user_permissions(self, token_str):
        try:
            token= UntypedToken(token_str)
            return set(token.payload.get('permissions') or []), token.payload.get('owner_id'), token.payload
        except Exception:
            return set(), None, {}

    def get_context_permissions(self, request):
        try:
            context = authorization_context_from_request(request)
        except Exception:
            return set()
        permissions = set(context.get("permissions") or [])
        wildcard_permissions = context.get("wildcard_permissions") or {}
        for wildcard in context.get("wildcards") or []:
            permissions.update(wildcard_permissions.get(wildcard) or [])
        return permissions

    @staticmethod
    def _matches_permission(required, granted_permissions):
        """Support scoped wildcard grants without making broad strings implicit."""
        return any(
            granted == required
            or (granted.endswith(".*") and required.startswith(granted[:-1]))
            for granted in granted_permissions
        )

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
        if token is not None and hasattr(token, "payload"):
            payload = token.payload
            if not validate_support_token(
                request.user,
                profile_id=payload.get("profile_id"),
                support_access_grant_id=payload.get("support_access_grant_id"),
            ):
                return False
            user_permissions = self.get_context_permissions(request)
            owner_id = payload.get("owner_id")
        else:
            auth_header = request.headers.get('Authorization', '')
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return False
            _, owner_id, payload = self.get_user_permissions(parts[1])
            user_permissions = self.get_context_permissions(request)
            if not validate_support_token(
                request.user,
                profile_id=payload.get("profile_id"),
                support_access_grant_id=payload.get("support_access_grant_id"),
            ):
                return False

        if owner_id and str(owner_id) == str(request.user.id):
            return True

        return self._matches_permission(permission, user_permissions)
        
class PermissionRequiredMixin:
    """
    Mixin to add permission checking to views
    """
    required_permission = None
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]

    
