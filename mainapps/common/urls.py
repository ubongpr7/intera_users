from django.urls import path
from .views import *
app_name='common'
urlpatterns = [
    path('',HomEPage.as_view(),name='home'),
    path('add/<str:app_name>/<str:company_id>/<str:model_name>/', GenericCreateView.as_view(), name='add_item'),
    path('list/<str:app_name>/<str:company_id>/<str:model_name>/', GenericList.as_view(), name='item_list'),
    path('delete/<str:app_name>/<str:company_id>/<str:model_name>/<int:pk>/', dynamic_delete, name='delete_item'),
    path('update/<str:app_name>/<str:company_id>/<str:model_name>/<int:pk>/', GenericUpdateView.as_view(), name='update_item'),
    
    
    path('get-regions/', get_regions, name='get_regions'),
    path('get-subregions/', get_subregions, name='get_subregions'),
    path('get-cities/', get_cities, name='get_cities'),
    path('get-units/', get_unit, name='get_units'),
    path('add-unit/', add_unit, name='add_unit'),

]
