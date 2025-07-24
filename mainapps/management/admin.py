from django.contrib import admin

from mainapps.utils.registrar import register_models,ProfileAgent
from .models import *
register_models(registerable_models)

# @admin.register(ProfileAgent)
# class ProfileAgentAdmin(admin.ModelAdmin):
#     list_disp
