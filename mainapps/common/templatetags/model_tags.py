from django import template
from django.apps import apps


register= template.Library()

@register.inclusion_tag('tags/item_tag.html')
def modelview_list(user):
    apps_list=[]
    exp_excluded_apps=['admin','auth','contenttypes','cities_light','accounts','sessions','messages','staticfiles','content_type_linking_models','permit','widget_tweaks','bootstrap5']
    excluded_apps=['admin','django_htmx','auth','contenttypes','cities_light','management','accounts','common','sessions','messages','staticfiles','content_type_linking_models','permit','widget_tweaks','bootstrap5', ]
    excluded_models=['CompanyAddress','Contact']
    for app in apps.get_app_configs():
        if app.label not in excluded_apps:
        
            models_list=[]

            for model in app.get_models():
                if model.__name__ not in excluded_models:
                    models_list.append(model.__name__)

            apps_list.append((app.label.title(),models_list))    
    return {'apps_list': apps_list,'user':user}    

@register.inclusion_tag('wrapper/tags/model_list.html')
def model_list(user):
    apps_list=[]
    excludeded_models=['contact', 'companyaddress','stocklocationtype','stockitemtracking']
    exp_excluded_apps=['admin','django_htmx','django_extensions','auth','contenttypes','management','common','cities_light','accounts','sessions','messages','staticfiles','content_type_linking_models','permit','widget_tweaks','bootstrap5']
    for app in apps.get_app_configs():
        if app.label not in exp_excluded_apps:
        
            models_list=[]

            for model in app.get_models():
                if model.__name__.lower() not in excludeded_models:
                    if model.__name__=="Company":
                        model=model.__name__
                    models_list.append(model)

            apps_list.append((app.label.title(),models_list))    
    return {'apps_list': apps_list,'user':user}    


@register.inclusion_tag('wrapper/tags/settings.html')
def settings(user):
    apps_list=[]
    settings_apps=['accounts','permit','permissions','management']
    for app in apps.get_app_configs():
        if app.label  in settings_apps:
        
            models_list=[]

            for model in app.get_models():
                models_list.append(model.__name__)

            apps_list.append((app.label.title(),models_list))    
    return {'settings_apps': apps_list,'user':user}    

@register.simple_tag(takes_context=True)
def current_user(context):
    print(context)
    return context