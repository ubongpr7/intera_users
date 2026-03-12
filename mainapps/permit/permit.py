from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)

from rest_framework_simplejwt.tokens import UntypedToken

class HasModelRequestPermission(permissions.BasePermission):
    """
    Microservice-adapted permission class that checks permissions via user service
    """
    def get_user_permissions(self, token_str):
        try:
            token= UntypedToken(token_str)
            return set(token.payload.get('permissions') or []), token.payload.get('owner_id')
        except Exception:
            return set(), None

    def has_permission(self, request, view):
        permission = getattr(view, 'required_permission', None)
        if not permission:
            return False

        if isinstance(permission, dict):
            action = getattr(view, "action", None)
            permission = permission.get(action)
            if not permission:
                return False

        if getattr(request.user, "is_superuser", False):
            return True

        token = getattr(request, "auth", None)
        if token is not None and hasattr(token, "payload"):
            user_permissions = set(token.payload.get("permissions") or [])
            owner_id = token.payload.get("owner_id")
        else:
            auth_header = request.headers.get('Authorization', '')
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return False
            user_permissions, owner_id = self.get_user_permissions(parts[1])

        if owner_id and str(owner_id) == str(request.user.id):
            return True

        return permission in user_permissions
        
class PermissionRequiredMixin:
    """
    Mixin to add permission checking to views
    """
    required_permission = None
    permission_classes = [permissions.IsAuthenticated, HasModelRequestPermission]

    
