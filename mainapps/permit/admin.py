from django.contrib import admin

# Register your models here.
from .models import PermissionCategory,CustomUserPermission

admin.site.register(PermissionCategory)
admin.site.register(CustomUserPermission)