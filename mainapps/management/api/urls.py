from django.urls import path
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [
    # path('activities/<str:user_id>/', views.UserActivityLogsAPIView.as_view(), name='create-company-address'),
    
    
    path('staff/roles/', views.CreateRoleView.as_view(), name='role-create'),
    path('staff/roles/<str:id>/', views.RoleDetailView.as_view(), name='role-detail'),
    path('staff/role/list/', views.StaffRoleView.as_view(), name='role-list'),
    path('roles/<str:role_id>/deactivate/', views.RoleDeactivateView.as_view(), name='role-deactivate'),
    
    path('staff/groups/', views.CreateGroupView.as_view(), name='group-create'),
    path('staff/group-details/<str:id>/', views.GroupDetailView.as_view(), name='group-detail'),
    path('staff/group/list/', views.StaffGroupView.as_view(), name='group-list'),

]

