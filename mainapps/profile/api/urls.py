from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyProfileAddressViewSet,
    CompanyProfileViewSet,
    InventoryPolicyViewSet,
    ProfileAgentSetupView,
    RecallPolicyViewSet,
    ReorderStrategyViewSet,
    StaffGroupViewSet,
    StaffRoleAssignmentViewSet,
    StaffRoleViewSet,
)

router = DefaultRouter()
router.register(r"profiles", CompanyProfileViewSet, basename="company-profile")
router.register(r"roles", StaffRoleViewSet, basename="staff-role")
router.register(r"groups", StaffGroupViewSet, basename="staff-group")
router.register(r"addresses", CompanyProfileAddressViewSet, basename="address")
router.register(r"assignments", StaffRoleAssignmentViewSet, basename="staff-role-assignment")
router.register(r"recall-policies", RecallPolicyViewSet, basename="recall-policy")
router.register(r"reorder-strategies", ReorderStrategyViewSet, basename="reorder-strategy")
router.register(r"inventory-policies", InventoryPolicyViewSet, basename="inventory-policy")

urlpatterns = [
    path("", include(router.urls)),
    path("agent-setup/", ProfileAgentSetupView.as_view(), name="profile-agent-setup"),
    path(
        "roles/<str:pk>/deactivate/",
        StaffRoleAssignmentViewSet.as_view({"post": "deactivate"}),
        name="role-deactivate",
    ),
]
