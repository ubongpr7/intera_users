from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyProfileViewSet,
    InventoryPolicyViewSet,
    RecallPolicyViewSet,
    ReorderStrategyViewSet,
    StaffRoleViewSet,
    StaffGroupViewSet,
    ActivityLogViewSet,
    CompanyProfileAddressViewSet,
)

router = DefaultRouter()

# Company profile endpoints
router.register(r'profiles', CompanyProfileViewSet, basename='company-profile')
router.register(r'roles', StaffRoleViewSet, basename='staff-role')
router.register(r'groups', StaffGroupViewSet, basename='staff-group')
router.register(r'addresses',     CompanyProfileAddressViewSet, basename='address')
router.register(r'activity-logs', ActivityLogViewSet, basename='activity-log')

# Policy endpoints
router.register(r'recall-policies', RecallPolicyViewSet, basename='recall-policy')
router.register(r'reorder-strategies', ReorderStrategyViewSet, basename='reorder-strategy')
router.register(r'inventory-policies', InventoryPolicyViewSet, basename='inventory-policy')

urlpatterns = [
    path('', include(router.urls)),
]
