from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentInstructionPresetViewSet,
    AgentSkillViewSet,
    AgentTemplateViewSet,
    AgentToolViewSet,
    ToolServerViewSet,
    WorkspaceToolConnectionViewSet,
    WorkspaceAgentRuntimeInternalRegistryView,
    WorkspaceAgentViewSet,
    WorkspaceAgentRuntimeViewSet,
)


router = DefaultRouter()
router.register(r"tool-servers", ToolServerViewSet, basename="agent-tool-server")
router.register(r"tool-connections", WorkspaceToolConnectionViewSet, basename="workspace-tool-connection")
router.register(r"tools", AgentToolViewSet, basename="agent-tool")
router.register(r"skills", AgentSkillViewSet, basename="agent-skill")
router.register(r"instruction-presets", AgentInstructionPresetViewSet, basename="agent-instruction-preset")
router.register(r"templates", AgentTemplateViewSet, basename="agent-template")
router.register(r"workspace-agents", WorkspaceAgentViewSet, basename="workspace-agent")
router.register(r"runtime/agents", WorkspaceAgentRuntimeViewSet, basename="runtime-agent")


urlpatterns = [
    path("runtime/internal/registry/", WorkspaceAgentRuntimeInternalRegistryView.as_view(), name="runtime-agent-internal-registry"),
    path("", include(router.urls)),
]
