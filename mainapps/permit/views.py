from django.shortcuts import render,HttpResponse
from .permit import *
from django.conf import settings
User= settings.AUTH_USER_MODEL
# Create your views here.
def permit_home(request):
    permisions=get_all_permissions()
    user_permission=get_model_permission(User)
    
    context= {
        'all_permisions': permisions,
        'userpermisions': user_permission,
    }
    return render(request,'permit.html',context) 