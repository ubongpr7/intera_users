from rest_framework import permissions
from mainapps.permit.models import CustomUserPermission
from django.db.models import Prefetch
class HasModelRequestPermission(permissions.BasePermission):
    """
    Checks for both company access AND specific permissions
    """
    def has_permission(self, request, view):
        if request.user.profile.owner == request.user:
            return True

        permission = getattr(view, 'required_permission', None)
        
        user_perms=set()

        user_perms.update(request.user.custom_permissions.all().values_list('codename', flat=True))
        try:
            from django.utils import timezone
            current_time = timezone.now()
            for role in request.user.roles.all().iterator():
                if role.start_date and role.end_date:
                    # Debug prints
                    print(f"Current time: {current_time}")
                    print(f"Role {role.id}: Start={role.start_date}, End={role.end_date}")

                    if role.end_date < current_time:
                        role.delete()
                        print(f"Deleted inactive role {role.id}")
                    else:
                        perms = role.role.permissions.all().values_list('codename', flat=True)
                        user_perms.update(perms)
        except Exception as e:
            print(f"Error: {e}")
        try:
            groups=request.user.staff_groups.all()
            for group in groups:
                user_perms.update(group.permissions.all().values_list('codename', flat=True))
        except Exception as e:
            print(e)
    
        if permission:
         
            if isinstance(permission, dict):
                action = view.action
                print(action)
                permission= permission.get(action)
            return permission in user_perms

            
        return False
