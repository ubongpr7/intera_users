from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GroupAccessViewSet,
    RoleAccessViewSet,
    RoleAssignmentViewSet,
    UserAccessViewSet,
)

router = DefaultRouter()
router.register(r"role-assignments", RoleAssignmentViewSet, basename="role-assignment")
router.register(r"users", UserAccessViewSet, basename="user-access")
router.register(r"groups", GroupAccessViewSet, basename="group-access")
router.register(r"roles", RoleAccessViewSet, basename="role-access")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "user/<str:pk>/groups/",
        UserAccessViewSet.as_view({"get": "groups", "put": "groups"}),
        name="manage-user-groups-legacy",
    ),
    path(
        "role-assignments/roles/",
        RoleAssignmentViewSet.as_view({"get": "list", "post": "create"}),
        name="legacy-role-assignment-list",
    ),
    path(
        "role-assignments/roles/<str:pk>/",
        RoleAssignmentViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="legacy-role-assignment-detail",
    ),
]
