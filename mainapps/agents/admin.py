from django.contrib import admin

from .models import (
    AgentInstructionPreset,
    AgentSkill,
    AgentTemplate,
    AgentTemplateSkillBinding,
    AgentTemplateToolBinding,
    AgentTool,
    ToolServer,
    WorkspaceAgent,
    WorkspaceAgentSkillBinding,
    WorkspaceAgentToolBinding,
)


class AgentTemplateSkillInline(admin.TabularInline):
    model = AgentTemplateSkillBinding
    extra = 0


class AgentTemplateToolInline(admin.TabularInline):
    model = AgentTemplateToolBinding
    extra = 0


class WorkspaceAgentSkillInline(admin.TabularInline):
    model = WorkspaceAgentSkillBinding
    extra = 0


class WorkspaceAgentToolInline(admin.TabularInline):
    model = WorkspaceAgentToolBinding
    extra = 0


@admin.register(ToolServer)
class ToolServerAdmin(admin.ModelAdmin):
    list_display = ("name", "server_id", "scope", "transport", "auth_mode", "health_status", "is_active")
    list_filter = ("scope", "transport", "auth_mode", "health_status", "is_active")
    search_fields = ("name", "server_id", "server_url")


@admin.register(AgentTool)
class AgentToolAdmin(admin.ModelAdmin):
    list_display = ("display_name", "key", "scope", "tool_server", "auth_mode", "health_status", "is_active")
    list_filter = ("scope", "auth_mode", "health_status", "is_active", "is_discoverable")
    search_fields = ("display_name", "key", "remote_tool_name")


@admin.register(AgentSkill)
class AgentSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "scope", "is_active")
    list_filter = ("scope", "is_active")
    search_fields = ("name", "key", "description")


@admin.register(AgentInstructionPreset)
class AgentInstructionPresetAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "instruction_type", "scope", "is_default", "is_active")
    list_filter = ("instruction_type", "scope", "is_default", "is_active")
    search_fields = ("title", "key", "description", "body")


@admin.register(AgentTemplate)
class AgentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "version", "is_active", "is_featured", "allow_workspace_installs")
    list_filter = ("is_active", "is_featured", "allow_workspace_installs", "preferred_transport")
    search_fields = ("name", "slug", "description")
    inlines = [AgentTemplateSkillInline, AgentTemplateToolInline]


@admin.register(WorkspaceAgent)
class WorkspaceAgentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "profile", "origin", "visibility", "routing_policy", "is_enabled")
    list_filter = ("origin", "visibility", "routing_policy", "is_enabled")
    search_fields = ("name", "slug", "description", "profile__name")
    inlines = [WorkspaceAgentSkillInline, WorkspaceAgentToolInline]

