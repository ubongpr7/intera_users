from datetime import timezone
from django.core.signing import Signer
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from mainapps.management.models import CompanyProfile, StaffPolicy

signer=Signer()


from django.http import HttpResponseForbidden


from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from mainapps.management.models import StaffPolicy

class CustomPermissionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            active_roles = request.user.staff_roles.through.objects.filter(
                user=request.user,
                start_time__lte=timezone.now(),
                end_time__gte=timezone.now()
            )

            if active_roles.exists():
                # User has active roles, use role permissions
                request.user.active_policies = StaffPolicy.objects.filter(roles__users=request.user).distinct()
            else:
                # No active roles, use group permissions
                request.user.active_policies = StaffPolicy.objects.filter(groups__users=request.user).distinct()

            # Object-level permissions
            request.user.object_permissions = {}
            for permission in request.user.object_permissions.all():
                request.user.object_permissions[permission.inventory.id] = permission.policies.all()

        return None

class CustomPermissionRequiredMixin:
    required_permission = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("You are not authenticated")

        if self.required_permission:
            if not self.check_permission(request):
                return HttpResponseForbidden("You do not have permission to access this resource")

        return super().dispatch(request, *args, **kwargs)

    def check_permission(self, request):
        # Check active roles first
        active_roles = request.user.staff_roles.through.objects.filter(
            user=request.user,
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        )

        if active_roles.exists():
            # User has active roles, use role permissions
            active_policies = StaffPolicy.objects.filter(roles__users=request.user).distinct()
        else:
            # No active roles, use group permissions
            active_policies = StaffPolicy.objects.filter(groups__users=request.user).distinct()

        # Check general permissions
        if active_policies.filter(name=self.required_permission).exists():
            return True

        # Check object-level permissions if applicable
        if hasattr(self, 'get_object'):
            obj = self.get_object()
            if hasattr(request.user, 'object_permissions') and obj.id in request.user.object_permissions:
                if request.user.object_permissions[obj.id].filter(name=self.required_permission).exists():
                    return True

        return False

def encrypt_data(data_to_be_encrypted ):
    return signer.sign(data_to_be_encrypted)

def decrypt_data(data_to_be_decrypted ):
    return signer.unsign(data_to_be_decrypted)

def management_dispatch_dispatcher(self, request):
    company_id=decrypt_data(self.kwargs['company_id'])

    try:
        self.company = get_object_or_404(CompanyProfile, unique_id=company_id)

        if hasattr(request.user,'company' ):
            if request.user.company !=self.company:
                print('thief! lol')
                if request.htmx:
                    return HttpResponse('<div id="error-message"><h2>404</h2> <h3>User does not have permission to carry out this action</h3></div>')
                return self.handle_no_permission()
        elif hasattr(self.request.user,'profile'):
            if request.user.profile != self.company:
                if request.htmx:
                    return HttpResponse('<div id="error-message" ><h2>404</h2> <h3>User does not have permission to carry out this action</h3></div>')
                return self.handle_no_permission()
        
    except Exception as e:    
        print(e)
        return self.handle_no_permission()
