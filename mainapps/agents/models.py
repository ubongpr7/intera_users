from __future__ import annotations

from copy import deepcopy
import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from mainapps.profile.models import CompanyProfile, ModelVersion


def _default_text_modes() -> list[str]:
    return ["text"]


def _default_capabilities() -> dict[str, Any]:
    return {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    }


class ScopeChoices(models.TextChoices):
    PLATFORM = "platform", "Platform"
    WORKSPACE = "workspace", "Workspace"


class ToolTransportChoices(models.TextChoices):
    MCP = "mcp", "MCP"
    NATIVE = "native", "Native"
    WEBHOOK = "webhook", "Webhook"
    MANUAL = "manual", "Manual"


class ToolAuthModeChoices(models.TextChoices):
    NONE = "none", "None"
    FORWARD_BEARER = "forward_bearer", "Forward Bearer"
    STATIC = "static", "Static"
    CONTEXT = "context", "Context"
    SERVICE_ACCOUNT = "service_account", "Service Account"
    CUSTOM = "custom", "Custom"


class ToolConnectionScopeChoices(models.TextChoices):
    WORKSPACE = "workspace", "Workspace"
    USER = "user", "User"


class ToolConnectionStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    CONNECTED = "connected", "Connected"
    EXPIRED = "expired", "Expired"
    ERROR = "error", "Error"
    REVOKED = "revoked", "Revoked"


class CatalogHealthChoices(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    HEALTHY = "healthy", "Healthy"
    DEGRADED = "degraded", "Degraded"
    UNAVAILABLE = "unavailable", "Unavailable"


class AgentOriginChoices(models.TextChoices):
    TEMPLATE = "template", "Template Installation"
    CUSTOM = "custom", "Custom"


class AgentVisibilityChoices(models.TextChoices):
    WORKSPACE = "workspace", "Workspace"
    PRIVATE = "private", "Private"


class AgentRoutingPolicyChoices(models.TextChoices):
    DIRECT = "direct", "Direct"
    ORCHESTRATED = "orchestrated", "Orchestrated"
    SPECIALIST_ONLY = "specialist_only", "Specialist Only"


class InstructionTypeChoices(models.TextChoices):
    SYSTEM = "system", "System"
    DEVELOPER = "developer", "Developer"
    ASSISTANT = "assistant", "Assistant"


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ScopedCatalogModel(TimestampedModel):
    scope = models.CharField(
        max_length=20,
        choices=ScopeChoices.choices,
        default=ScopeChoices.PLATFORM,
        db_index=True,
    )
    profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_items",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_%(class)s_items",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_%(class)s_items",
    )

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        if self.scope == ScopeChoices.WORKSPACE and self.profile is None:
            raise ValidationError({"profile": "Workspace-scoped records require a profile."})
        if self.scope == ScopeChoices.PLATFORM and self.profile_id is not None:
            raise ValidationError({"profile": "Platform-scoped records cannot be attached to a profile."})


class ToolServer(ScopedCatalogModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    server_id = models.CharField(max_length=120)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    transport = models.CharField(
        max_length=20,
        choices=ToolTransportChoices.choices,
        default=ToolTransportChoices.MCP,
    )
    server_url = models.CharField(max_length=500, blank=True)
    tool_name_prefix = models.CharField(max_length=120, blank=True)
    auth_mode = models.CharField(
        max_length=30,
        choices=ToolAuthModeChoices.choices,
        default=ToolAuthModeChoices.NONE,
    )
    auth_config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    health_status = models.CharField(
        max_length=20,
        choices=CatalogHealthChoices.choices,
        default=CatalogHealthChoices.UNKNOWN,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scope", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["server_id"],
                condition=Q(scope=ScopeChoices.PLATFORM),
                name="agents_unique_platform_tool_server_id",
            ),
            models.UniqueConstraint(
                fields=["profile", "server_id"],
                condition=Q(scope=ScopeChoices.WORKSPACE),
                name="agents_unique_workspace_tool_server_id",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class WorkspaceToolConnection(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="tool_connections",
    )
    tool_server = models.ForeignKey(
        ToolServer,
        on_delete=models.CASCADE,
        related_name="workspace_connections",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    connection_scope = models.CharField(
        max_length=20,
        choices=ToolConnectionScopeChoices.choices,
        default=ToolConnectionScopeChoices.WORKSPACE,
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_tool_connections",
    )
    auth_type = models.CharField(max_length=50, blank=True)
    server_url_override = models.CharField(max_length=500, blank=True)
    credential_payload_encrypted = models.TextField(blank=True)
    access_token_encrypted = models.TextField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    granted_scopes = models.JSONField(default=list, blank=True)
    resource_owner_id = models.CharField(max_length=255, blank=True)
    resource_label = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ToolConnectionStatusChoices.choices,
        default=ToolConnectionStatusChoices.PENDING,
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tool_connections",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_tool_connections",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "slug"],
                name="agents_unique_workspace_tool_connection_slug",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.connection_scope == ToolConnectionScopeChoices.USER and self.owner_user_id is None:
            raise ValidationError({"owner_user": "User-scoped tool connections require an owner user."})
        if self.connection_scope == ToolConnectionScopeChoices.WORKSPACE and self.owner_user_id is not None:
            raise ValidationError({"owner_user": "Workspace-scoped tool connections cannot have an owner user."})

    def __str__(self) -> str:
        return self.name


class AgentTool(ScopedCatalogModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tool_server = models.ForeignKey(
        ToolServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tools",
    )
    remote_tool_name = models.CharField(max_length=255)
    auth_mode = models.CharField(
        max_length=30,
        choices=ToolAuthModeChoices.choices,
        default=ToolAuthModeChoices.NONE,
    )
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_discoverable = models.BooleanField(default=True)
    health_status = models.CharField(
        max_length=20,
        choices=CatalogHealthChoices.choices,
        default=CatalogHealthChoices.UNKNOWN,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scope", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["key"],
                condition=Q(scope=ScopeChoices.PLATFORM),
                name="agents_unique_platform_tool_key",
            ),
            models.UniqueConstraint(
                fields=["profile", "key"],
                condition=Q(scope=ScopeChoices.WORKSPACE),
                name="agents_unique_workspace_tool_key",
            ),
        ]

    @property
    def full_tool_name(self) -> str:
        prefix = (self.tool_server.tool_name_prefix or "").strip() if self.tool_server else ""
        if prefix and not self.remote_tool_name.startswith(prefix):
            return f"{prefix}{self.remote_tool_name}"
        return self.remote_tool_name

    def __str__(self) -> str:
        return self.display_name


class AgentSkill(ScopedCatalogModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    examples = models.JSONField(default=list, blank=True)
    input_modes = models.JSONField(default=_default_text_modes, blank=True)
    output_modes = models.JSONField(default=_default_text_modes, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["scope", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["key"],
                condition=Q(scope=ScopeChoices.PLATFORM),
                name="agents_unique_platform_skill_key",
            ),
            models.UniqueConstraint(
                fields=["profile", "key"],
                condition=Q(scope=ScopeChoices.WORKSPACE),
                name="agents_unique_workspace_skill_key",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class AgentInstructionPreset(ScopedCatalogModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instruction_type = models.CharField(
        max_length=20,
        choices=InstructionTypeChoices.choices,
        default=InstructionTypeChoices.SYSTEM,
    )
    body = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["scope", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["key"],
                condition=Q(scope=ScopeChoices.PLATFORM),
                name="agents_unique_platform_instruction_key",
            ),
            models.UniqueConstraint(
                fields=["profile", "key"],
                condition=Q(scope=ScopeChoices.WORKSPACE),
                name="agents_unique_workspace_instruction_key",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class A2AAgentDefinitionMixin(TimestampedModel):
    protocol_version = models.CharField(max_length=20, default="0.3.0")
    slug = models.SlugField(max_length=120)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    preferred_transport = models.CharField(max_length=50, default="kafka")
    provider_organization = models.CharField(max_length=255, blank=True)
    provider_url = models.CharField(max_length=500, blank=True)
    version = models.CharField(max_length=50, default="0.1.0")
    documentation_url = models.URLField(blank=True)
    icon_url = models.URLField(blank=True)
    additional_interfaces = models.JSONField(default=list, blank=True)
    capabilities = models.JSONField(default=_default_capabilities, blank=True)
    security_schemes = models.JSONField(default=dict, blank=True)
    security = models.JSONField(default=list, blank=True)
    supports_authenticated_extended_card = models.BooleanField(default=True)
    default_input_modes = models.JSONField(default=_default_text_modes, blank=True)
    default_output_modes = models.JSONField(default=_default_text_modes, blank=True)
    system_instruction = models.TextField(blank=True)
    developer_instruction = models.TextField(blank=True)
    assistant_instruction = models.TextField(blank=True)
    llm_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_definitions",
    )
    llm_temperature = models.FloatField(default=0.2)
    max_reasoning_steps = models.PositiveSmallIntegerField(default=5)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def build_agent_card_payload(
        self,
        *,
        card_name: str | None = None,
        card_url: str | None = None,
        metadata_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_name = (card_name or self.slug).strip()
        resolved_url = (card_url or self.url or f"{self.preferred_transport}://{resolved_name}").strip()
        payload: dict[str, Any] = {
            "protocolVersion": self.protocol_version,
            "name": resolved_name,
            "description": self.description,
            "url": resolved_url,
            "preferredTransport": self.preferred_transport,
            "version": self.version,
            "capabilities": self.capabilities or {},
            "defaultInputModes": self.default_input_modes or ["text"],
            "defaultOutputModes": self.default_output_modes or ["text"],
        }
        if self.provider_organization or self.provider_url:
            payload["provider"] = {
                "organization": self.provider_organization or None,
                "url": self.provider_url or None,
            }
        if self.documentation_url:
            payload["documentationUrl"] = self.documentation_url
        if self.icon_url:
            payload["iconUrl"] = self.icon_url
        if self.additional_interfaces:
            payload["additionalInterfaces"] = self.additional_interfaces
        if self.security_schemes:
            payload["securitySchemes"] = self.security_schemes
        if self.security:
            payload["security"] = self.security
        if self.supports_authenticated_extended_card:
            payload["supportsAuthenticatedExtendedCard"] = True

        skills_payload: list[dict[str, Any]] = []
        skill_bindings = getattr(self, "skill_bindings", None)
        skill_iterable = (
            skill_bindings.select_related("skill").order_by("order", "created_at") if skill_bindings is not None else []
        )
        for binding in skill_iterable:
            skill = binding.skill
            skills_payload.append(
                {
                    "id": skill.key,
                    "name": skill.name,
                    "description": skill.description,
                    "tags": skill.tags or [],
                    "examples": skill.examples or [],
                    "inputModes": skill.input_modes or ["text"],
                    "outputModes": skill.output_modes or ["text"],
                }
            )
        if skills_payload:
            payload["skills"] = skills_payload

        tool_payload: list[dict[str, Any]] = []
        tool_bindings = getattr(self, "tool_bindings", None)
        tool_iterable = (
            tool_bindings.select_related("tool", "tool__tool_server").order_by("order", "created_at")
            if tool_bindings is not None
            else []
        )
        for binding in tool_iterable:
            tool = binding.tool
            tool_payload.append(
                {
                    "key": tool.key,
                    "name": tool.full_tool_name,
                    "displayName": tool.display_name,
                    "description": tool.description,
                    "required": binding.is_required,
                    "toolServerId": getattr(tool.tool_server, "server_id", None),
                }
            )
        if tool_payload:
            payload.setdefault("metadata", {})
            payload["metadata"]["tools"] = tool_payload
        if metadata_overrides:
            payload.setdefault("metadata", {})
            payload["metadata"].update(metadata_overrides)

        return payload


class AgentTemplate(A2AAgentDefinitionMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    allow_workspace_installs = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_agent_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_agent_templates",
    )
    skills = models.ManyToManyField(
        AgentSkill,
        through="AgentTemplateSkillBinding",
        related_name="template_agents",
        blank=True,
    )
    tools = models.ManyToManyField(
        AgentTool,
        through="AgentTemplateToolBinding",
        related_name="template_agents",
        blank=True,
    )

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["slug"], name="agents_unique_template_slug"),
        ]

    def __str__(self) -> str:
        return self.name


class WorkspaceAgent(A2AAgentDefinitionMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="workspace_agents",
    )
    source_template = models.ForeignKey(
        AgentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workspace_agents",
    )
    origin = models.CharField(
        max_length=20,
        choices=AgentOriginChoices.choices,
        default=AgentOriginChoices.CUSTOM,
    )
    visibility = models.CharField(
        max_length=20,
        choices=AgentVisibilityChoices.choices,
        default=AgentVisibilityChoices.WORKSPACE,
    )
    routing_policy = models.CharField(
        max_length=30,
        choices=AgentRoutingPolicyChoices.choices,
        default=AgentRoutingPolicyChoices.DIRECT,
    )
    is_enabled = models.BooleanField(default=True)
    template_version_snapshot = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workspace_agents",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_workspace_agents",
    )
    skills = models.ManyToManyField(
        AgentSkill,
        through="WorkspaceAgentSkillBinding",
        related_name="workspace_agents",
        blank=True,
    )
    tools = models.ManyToManyField(
        AgentTool,
        through="WorkspaceAgentToolBinding",
        related_name="workspace_agents",
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "slug"], name="agents_unique_workspace_agent_slug"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.origin == AgentOriginChoices.TEMPLATE and self.source_template is None:
            raise ValidationError({"source_template": "Template-based workspace agents require a source template."})

    def build_runtime_name(self) -> str:
        return f"wa-p{self.profile_id}-{self.slug}-{self.id.hex[:12]}"

    def build_runtime_metadata(self) -> dict[str, Any]:
        return {
            "ka2aRuntime": {
                "runtimeName": self.build_runtime_name(),
                "publicSlug": self.slug,
                "workspaceAgentId": str(self.id),
                "profileId": self.profile_id,
                "visibility": self.visibility,
            }
        }

    def build_runtime_card_payload(self) -> dict[str, Any]:
        runtime_name = self.build_runtime_name()
        return self.build_agent_card_payload(
            card_name=runtime_name,
            card_url=self.url or f"{self.preferred_transport}://{runtime_name}",
            metadata_overrides=self.build_runtime_metadata(),
        )

    def build_runtime_config(self) -> dict[str, Any]:
        template_runtime = {}
        if self.source_template_id and isinstance(getattr(self.source_template, "metadata", None), dict):
            template_runtime = deepcopy((self.source_template.metadata or {}).get("runtime") or {})
        runtime_config = template_runtime
        runtime_config.update(deepcopy((self.metadata or {}).get("runtime") or {}))
        runtime_config.setdefault("processor", "langgraph-chat")
        runtime_config.setdefault("runtimeName", self.build_runtime_name())
        runtime_config.setdefault("publicSlug", self.slug)
        runtime_config.setdefault("profileId", self.profile_id)
        runtime_config.setdefault("workspaceAgentId", str(self.id))
        runtime_config.setdefault("visibility", self.visibility)
        return runtime_config

    def __str__(self) -> str:
        return f"{self.profile_id}:{self.name}"


class AgentTemplateSkillBinding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        AgentTemplate,
        on_delete=models.CASCADE,
        related_name="skill_bindings",
    )
    skill = models.ForeignKey(
        AgentSkill,
        on_delete=models.CASCADE,
        related_name="template_bindings",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["template", "skill"], name="agents_unique_template_skill_binding"),
        ]


class AgentTemplateToolBinding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        AgentTemplate,
        on_delete=models.CASCADE,
        related_name="tool_bindings",
    )
    tool = models.ForeignKey(
        AgentTool,
        on_delete=models.CASCADE,
        related_name="template_bindings",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    tool_config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["template", "tool"], name="agents_unique_template_tool_binding"),
        ]


class WorkspaceAgentSkillBinding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        WorkspaceAgent,
        on_delete=models.CASCADE,
        related_name="skill_bindings",
    )
    skill = models.ForeignKey(
        AgentSkill,
        on_delete=models.CASCADE,
        related_name="workspace_bindings",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["agent", "skill"], name="agents_unique_workspace_skill_binding"),
        ]


class WorkspaceAgentToolBinding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        WorkspaceAgent,
        on_delete=models.CASCADE,
        related_name="tool_bindings",
    )
    tool = models.ForeignKey(
        AgentTool,
        on_delete=models.CASCADE,
        related_name="workspace_bindings",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    tool_config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["agent", "tool"], name="agents_unique_workspace_tool_binding"),
        ]
