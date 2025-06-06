from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import ListView
class CheckGroupPermission:
    def dispatch(self, request,*args,**kwargs):
        if request.user.groups.filter(name= 'group_name'):
            return super().dispatch(request,*args,**kwargs)
        else:
            raise PermissionDenied 
        

# usage

class ModelItem(CheckGroupPermission,ListView):
    pass


# check permission directly

class SModelItem(PermissionRequiredMixin,ListView):
    pass 