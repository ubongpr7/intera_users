from django.urls import path
from .views import RoleAssignmentManager, UserGroupManager, UserPermissionManager,GroupPermissionManager,RolePermissionManager
from rest_framework.routers import DefaultRouter
from django.urls import path, include
router= DefaultRouter()
router.register(r'roles', RoleAssignmentManager, basename='role-assignment')
urlpatterns = [
    path('role-assignments/', include(router.urls)),
    path(
        'users/<str:pk>/permissions/',
        UserPermissionManager.as_view(),
        name='user-permissions-manage'
    ),
    path(
        'groups/<str:pk>/permissions/',
        GroupPermissionManager.as_view(),
        name='group-permissions-manage'
    ),
    path(
        'roles/<str:pk>/permissions/',
        RolePermissionManager.as_view(),
        name='role-permissions-manage'
    ),
    path(
        'user/<str:pk>/groups/',
        UserGroupManager.as_view(),
        name='manage-user-groups-'
    ),

]

