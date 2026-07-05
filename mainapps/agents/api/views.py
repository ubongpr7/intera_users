from __future__ import annotations

import json
import os
import secrets
from copy import deepcopy

from asgiref.sync import async_to_sync
from django.utils import timezone
from django.db import transaction
from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from mainapps.common.settings import get_company_or_profile
from mainapps.permit.permit import HasModelRequestPermission, PermissionRequiredMixin
from subapps.utils.request_context import (
    get_request_profile_id,
    get_request_support_access_grant_id,
)

from mainapps.agents.models import (
    AgentVisibilityChoices,
    AgentInstructionPreset,
    AgentSkill,
    AgentTemplate,
    AgentTemplateSkillBinding,
    AgentTemplateToolBinding,
    AgentTool,
    ScopeChoices,
    ToolServer,
    WorkspaceAgent,
    WorkspaceAgentSkillBinding,
    WorkspaceAgentToolBinding,
    WorkspaceToolConnection,
)

from .serializers import (
    AgentInstructionPresetSerializer,
    AgentSkillSerializer,
    AgentTemplateSerializer,
    AgentToolSerializer,
    InstallAgentTemplateSerializer,
    ToolServerSerializer,
    WorkspaceAgentReadSerializer,
    WorkspaceAgentRuntimeConfigSerializer,
    WorkspaceAgentRuntimeInternalSerializer,
    WorkspaceAgentRuntimeSummarySerializer,
    WorkspaceAgentSkillBindingWriteSerializer,
    WorkspaceAgentToolBindingWriteSerializer,
    WorkspaceAgentWriteSerializer,
    WorkspaceToolConnectionReadSerializer,
    WorkspaceToolConnectionWriteSerializer,
)


def _decrypt_secret(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if not raw.startswith("gAAAA"):
        return raw
    try:
        from cryptography.fernet import Fernet

        key = (os.getenv("FERNET_KEY") or "").strip()
        if not key:
            return raw
        return Fernet(key).decrypt(raw.encode()).decode()
    except Exception:
        return raw


def _decrypt_json_payload(value: str) -> dict[str, object]:
    raw = _decrypt_secret(value)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_runtime_headers(connection: WorkspaceToolConnection) -> dict[str, str]:
    payload = _decrypt_json_payload(connection.credential_payload_encrypted)
    headers: dict[str, str] = {}

    raw_headers = payload.get("headers")
    if isinstance(raw_headers, dict):
        for key, value in raw_headers.items():
            header_name = str(key or "").strip()
            header_value = str(value or "").strip()
            if header_name and header_value:
                headers[header_name] = header_value

    token = _decrypt_secret(connection.access_token_encrypted)
    if not token:
        token = str(
            payload.get("api_key")
            or payload.get("apiKey")
            or payload.get("token")
            or payload.get("value")
            or payload.get("secret")
            or ""
        ).strip()
    if token:
        header_name = str(payload.get("header_name") or payload.get("headerName") or "authorization").strip() or "authorization"
        default_scheme = "Bearer" if header_name.lower() == "authorization" else ""
        scheme = str(payload.get("scheme") or default_scheme).strip()
        headers[header_name] = f"{scheme} {token}".strip() if scheme else token

    return headers


def _require_mcp():
    try:
        import httpx  # type: ignore
        from mcp import ClientSession  # type: ignore
        from mcp.client.streamable_http import streamable_http_client  # type: ignore
    except Exception as exc:
        raise RuntimeError("MCP client extras are not installed in users service.") from exc
    return httpx, ClientSession, streamable_http_client


async def _probe_mcp_server(*, server_url: str, headers: dict[str, str], timeout_s: float = 15.0) -> dict[str, object]:
    httpx, ClientSession, streamable_http_client = _require_mcp()

    async with httpx.AsyncClient(
        headers=headers,
        timeout=float(timeout_s),
        follow_redirects=True,
    ) as client:
        async with streamable_http_client(server_url, http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

    raw_tools = result.get("tools", result) if isinstance(result, dict) else getattr(result, "tools", result)
    tool_names: list[str] = []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            name = getattr(item, "name", None) if not isinstance(item, dict) else item.get("name")
            if isinstance(name, str) and name.strip():
                tool_names.append(name.strip())

    return {
        "tool_count": len(tool_names),
        "sample_tools": tool_names[:10],
    }


def _profile_from_request(request):
    profile_id = get_request_profile_id(request, required=True, as_str=False)
    profile = get_company_or_profile(
        request.user,
        profile_id=profile_id,
        support_access_grant_id=get_request_support_access_grant_id(request),
    )
    if not profile:
        raise PermissionDenied("Profile context is not accessible for this user.")
    return profile


def _require_runtime_shared_token(request):
    expected = (os.getenv("KA2A_RUNTIME_SHARED_TOKEN") or "").strip()
    provided = (request.headers.get("X-KA2A-Runtime-Token") or "").strip()
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise PermissionDenied("Runtime sync token is invalid.")


def _catalog_queryset(model, *, profile):
    return model.objects.filter(
        is_active=True,
    ).filter(
        Q(scope=ScopeChoices.PLATFORM) | Q(scope=ScopeChoices.WORKSPACE, profile=profile)
    )


def _runtime_agent_queryset(*, profile, user):
    return WorkspaceAgent.objects.filter(
        profile=profile,
        is_enabled=True,
    ).filter(
        Q(visibility=AgentVisibilityChoices.WORKSPACE)
        | Q(visibility=AgentVisibilityChoices.PRIVATE, created_by=user)
    )


class ToolServerViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ToolServer.objects.all().order_by("scope", "name")
    serializer_class = ToolServerSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
    }
    search_fields = ["name", "server_id", "server_url"]
    ordering_fields = ["name", "updated_at"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return _catalog_queryset(ToolServer, profile=profile)


class WorkspaceToolConnectionViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = WorkspaceToolConnection.objects.select_related("profile", "tool_server", "owner_user").all().order_by("name")
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
        "create": "manage_agent_settings",
        "update": "manage_agent_settings",
        "partial_update": "manage_agent_settings",
        "destroy": "manage_agent_settings",
        "test_connection": "manage_agent_settings",
    }
    search_fields = ["name", "slug", "resource_label", "resource_owner_id"]
    ordering_fields = ["name", "updated_at", "created_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return (
            WorkspaceToolConnection.objects.filter(profile=profile)
            .select_related("profile", "tool_server", "owner_user")
            .order_by("name")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return WorkspaceToolConnectionReadSerializer
        return WorkspaceToolConnectionWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = self.get_queryset().get(pk=serializer.instance.pk)
        headers = self.get_success_headers(serializer.data)
        return Response(
            WorkspaceToolConnectionReadSerializer(instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        refreshed = self.get_queryset().get(pk=instance.pk)
        return Response(
            WorkspaceToolConnectionReadSerializer(refreshed).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        serializer.save(
            profile=profile,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        connection = self.get_object()
        server_url = str(connection.server_url_override or connection.tool_server.server_url or "").strip()
        if not server_url:
            raise ValidationError({"server_url_override": "No MCP server URL is configured for this connection."})

        headers = _build_runtime_headers(connection)
        try:
            result = async_to_sync(_probe_mcp_server)(
                server_url=server_url,
                headers=headers,
                timeout_s=15.0,
            )
        except Exception as exc:
            connection.status = "error"
            connection.last_tested_at = timezone.now()
            connection.last_error = str(exc)
            connection.updated_by = request.user
            connection.save(update_fields=["status", "last_tested_at", "last_error", "updated_by", "updated_at"])
            return Response(
                {
                    "ok": False,
                    "server_url": server_url,
                    "header_names": sorted(headers.keys()),
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection.status = "connected"
        connection.last_tested_at = timezone.now()
        connection.last_error = ""
        connection.updated_by = request.user
        connection.save(update_fields=["status", "last_tested_at", "last_error", "updated_by", "updated_at"])
        return Response(
            {
                "ok": True,
                "server_url": server_url,
                "header_names": sorted(headers.keys()),
                **result,
            },
            status=status.HTTP_200_OK,
        )


class AgentToolViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AgentTool.objects.select_related("tool_server").all().order_by("scope", "display_name")
    serializer_class = AgentToolSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
    }
    search_fields = ["display_name", "key", "remote_tool_name", "description"]
    ordering_fields = ["display_name", "updated_at", "last_synced_at"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return _catalog_queryset(AgentTool, profile=profile).select_related("tool_server")


class AgentSkillViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AgentSkill.objects.all().order_by("scope", "name")
    serializer_class = AgentSkillSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
    }
    search_fields = ["name", "key", "description"]
    ordering_fields = ["name", "updated_at"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return _catalog_queryset(AgentSkill, profile=profile)


class AgentInstructionPresetViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AgentInstructionPreset.objects.all().order_by("scope", "title")
    serializer_class = AgentInstructionPresetSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
    }
    search_fields = ["title", "key", "description", "body"]
    ordering_fields = ["title", "updated_at"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return _catalog_queryset(AgentInstructionPreset, profile=profile)


class AgentTemplateViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AgentTemplate.objects.all()
    serializer_class = AgentTemplateSerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
        "card": "manage_agent_settings",
        "install": "manage_agent_settings",
    }
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["sort_order", "name", "updated_at"]
    ordering = ["sort_order", "name"]

    def get_queryset(self):
        _profile_from_request(self.request)
        return (
            AgentTemplate.objects.filter(is_active=True, allow_workspace_installs=True)
            .prefetch_related(
                Prefetch("skill_bindings", queryset=AgentTemplateSkillBinding.objects.select_related("skill").order_by("order", "created_at")),
                Prefetch(
                    "tool_bindings",
                    queryset=AgentTemplateToolBinding.objects.select_related("tool", "tool__tool_server").order_by("order", "created_at"),
                ),
            )
            .order_by("sort_order", "name")
        )

    @action(detail=True, methods=["get"])
    def card(self, request, pk=None):
        template = self.get_object()
        return Response(template.build_agent_card_payload(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def install(self, request, pk=None):
        profile = _profile_from_request(request)
        template = self.get_object()
        serializer = InstallAgentTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        slug = serializer.validated_data.get("slug") or template.slug
        if WorkspaceAgent.objects.filter(profile=profile, slug=slug).exists():
            raise ValidationError({"slug": "A workspace agent with this slug already exists."})

        agent = WorkspaceAgent.objects.create(
            profile=profile,
            source_template=template,
            origin="template",
            visibility=serializer.validated_data.get("visibility", "workspace"),
            routing_policy=serializer.validated_data.get("routing_policy", "direct"),
            slug=slug,
            name=serializer.validated_data.get("name") or template.name,
            description=serializer.validated_data.get("description", template.description),
            protocol_version=template.protocol_version,
            preferred_transport=template.preferred_transport,
            url=template.url,
            provider_organization=template.provider_organization,
            provider_url=template.provider_url,
            version=template.version,
            documentation_url=template.documentation_url,
            icon_url=template.icon_url,
            additional_interfaces=deepcopy(template.additional_interfaces),
            capabilities=deepcopy(template.capabilities),
            security_schemes=deepcopy(template.security_schemes),
            security=deepcopy(template.security),
            supports_authenticated_extended_card=template.supports_authenticated_extended_card,
            default_input_modes=deepcopy(template.default_input_modes),
            default_output_modes=deepcopy(template.default_output_modes),
            system_instruction=serializer.validated_data.get("system_instruction", template.system_instruction),
            developer_instruction=serializer.validated_data.get("developer_instruction", template.developer_instruction),
            assistant_instruction=serializer.validated_data.get("assistant_instruction", template.assistant_instruction),
            llm_version=template.llm_version,
            llm_temperature=template.llm_temperature,
            max_reasoning_steps=template.max_reasoning_steps,
            metadata=deepcopy(template.metadata),
            is_enabled=serializer.validated_data.get("is_enabled", True),
            template_version_snapshot=template.version,
            created_by=request.user,
            updated_by=request.user,
        )

        for binding in template.skill_bindings.select_related("skill").order_by("order", "created_at"):
            WorkspaceAgentSkillBinding.objects.create(
                agent=agent,
                skill=binding.skill,
                order=binding.order,
                is_primary=binding.is_primary,
                metadata=deepcopy(binding.metadata),
            )

        for binding in template.tool_bindings.select_related("tool").order_by("order", "created_at"):
            WorkspaceAgentToolBinding.objects.create(
                agent=agent,
                tool=binding.tool,
                order=binding.order,
                is_required=binding.is_required,
                tool_config=deepcopy(binding.tool_config),
            )

        response = WorkspaceAgentReadSerializer(
            WorkspaceAgent.objects.select_related("source_template", "llm_version")
            .prefetch_related(
                "skill_bindings__skill",
                "tool_bindings__tool__tool_server",
            )
            .get(pk=agent.pk)
        )
        return Response(response.data, status=status.HTTP_201_CREATED)


class WorkspaceAgentViewSet(PermissionRequiredMixin, viewsets.ModelViewSet):
    queryset = WorkspaceAgent.objects.all()
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "manage_agent_settings",
        "retrieve": "manage_agent_settings",
        "create": "manage_agent_settings",
        "update": "manage_agent_settings",
        "partial_update": "manage_agent_settings",
        "destroy": "manage_agent_settings",
        "card": "manage_agent_settings",
        "attach_tool": "manage_agent_settings",
        "detach_tool": "manage_agent_settings",
        "attach_skill": "manage_agent_settings",
        "detach_skill": "manage_agent_settings",
    }
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "updated_at", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return (
            WorkspaceAgent.objects.filter(profile=profile)
            .select_related("profile", "source_template", "llm_version")
            .prefetch_related(
                Prefetch("skill_bindings", queryset=WorkspaceAgentSkillBinding.objects.select_related("skill").order_by("order", "created_at")),
                Prefetch(
                    "tool_bindings",
                    queryset=WorkspaceAgentToolBinding.objects.select_related("tool", "tool__tool_server").order_by("order", "created_at"),
                ),
            )
            .order_by("name")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return WorkspaceAgentReadSerializer
        return WorkspaceAgentWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = self.get_queryset().get(pk=serializer.instance.pk)
        headers = self.get_success_headers(serializer.data)
        return Response(
            WorkspaceAgentReadSerializer(instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        refreshed = self.get_queryset().get(pk=instance.pk)
        return Response(
            WorkspaceAgentReadSerializer(refreshed).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        profile = _profile_from_request(self.request)
        serializer.save(
            profile=profile,
            origin="custom",
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["get"])
    def card(self, request, pk=None):
        agent = self.get_object()
        return Response(agent.build_agent_card_payload(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def attach_tool(self, request, pk=None):
        profile = _profile_from_request(request)
        agent = self.get_object()
        serializer = WorkspaceAgentToolBindingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tool = _catalog_queryset(AgentTool, profile=profile).filter(pk=serializer.validated_data["tool_id"]).first()
        if tool is None:
            raise ValidationError({"tool_id": "Tool is not available in this workspace scope."})

        binding, _ = WorkspaceAgentToolBinding.objects.update_or_create(
            agent=agent,
            tool=tool,
            defaults={
                "order": serializer.validated_data.get("order", agent.tool_bindings.count()),
                "is_required": serializer.validated_data.get("is_required", False),
                "tool_config": serializer.validated_data.get("tool_config", {}),
            },
        )
        return Response(
            WorkspaceAgentReadSerializer(self.get_queryset().get(pk=agent.pk)).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def detach_tool(self, request, pk=None):
        profile = _profile_from_request(request)
        agent = self.get_object()
        serializer = WorkspaceAgentToolBindingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tool = _catalog_queryset(AgentTool, profile=profile).filter(pk=serializer.validated_data["tool_id"]).first()
        if tool is None:
            raise ValidationError({"tool_id": "Tool is not available in this workspace scope."})

        WorkspaceAgentToolBinding.objects.filter(agent=agent, tool=tool).delete()
        return Response(
            WorkspaceAgentReadSerializer(self.get_queryset().get(pk=agent.pk)).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def attach_skill(self, request, pk=None):
        profile = _profile_from_request(request)
        agent = self.get_object()
        serializer = WorkspaceAgentSkillBindingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        skill = _catalog_queryset(AgentSkill, profile=profile).filter(pk=serializer.validated_data["skill_id"]).first()
        if skill is None:
            raise ValidationError({"skill_id": "Skill is not available in this workspace scope."})

        WorkspaceAgentSkillBinding.objects.update_or_create(
            agent=agent,
            skill=skill,
            defaults={
                "order": serializer.validated_data.get("order", agent.skill_bindings.count()),
                "is_primary": serializer.validated_data.get("is_primary", False),
                "metadata": serializer.validated_data.get("metadata", {}),
            },
        )
        return Response(
            WorkspaceAgentReadSerializer(self.get_queryset().get(pk=agent.pk)).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def detach_skill(self, request, pk=None):
        profile = _profile_from_request(request)
        agent = self.get_object()
        serializer = WorkspaceAgentSkillBindingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        skill = _catalog_queryset(AgentSkill, profile=profile).filter(pk=serializer.validated_data["skill_id"]).first()
        if skill is None:
            raise ValidationError({"skill_id": "Skill is not available in this workspace scope."})

        WorkspaceAgentSkillBinding.objects.filter(agent=agent, skill=skill).delete()
        return Response(
            WorkspaceAgentReadSerializer(self.get_queryset().get(pk=agent.pk)).data,
            status=status.HTTP_200_OK,
        )


class WorkspaceAgentRuntimeViewSet(PermissionRequiredMixin, viewsets.ReadOnlyModelViewSet):
    queryset = WorkspaceAgent.objects.all()
    serializer_class = WorkspaceAgentRuntimeSummarySerializer
    permission_classes = [IsAuthenticated, HasModelRequestPermission]
    required_permission = {
        "list": "interact_with_agent",
        "retrieve": "interact_with_agent",
        "registry": "interact_with_agent",
        "card": "interact_with_agent",
        "config": "interact_with_agent",
    }
    lookup_field = "slug"
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "updated_at", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        profile = _profile_from_request(self.request)
        return (
            _runtime_agent_queryset(profile=profile, user=self.request.user)
            .select_related("profile", "source_template", "llm_version")
            .prefetch_related(
                Prefetch("skill_bindings", queryset=WorkspaceAgentSkillBinding.objects.select_related("skill").order_by("order", "created_at")),
                Prefetch(
                    "tool_bindings",
                    queryset=WorkspaceAgentToolBinding.objects.select_related("tool", "tool__tool_server").order_by("order", "created_at"),
                ),
            )
            .order_by("name")
        )

    @action(detail=False, methods=["get"])
    def registry(self, request):
        profile = _profile_from_request(request)
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "profile_id": profile.id,
                "workspace_name": profile.name,
                "agent_count": len(serializer.data),
                "agents": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def card(self, request, slug=None):
        agent = self.get_object()
        return Response(agent.build_agent_card_payload(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def config(self, request, slug=None):
        agent = self.get_object()
        return Response(
            WorkspaceAgentRuntimeConfigSerializer(agent).data,
            status=status.HTTP_200_OK,
        )


class WorkspaceAgentRuntimeInternalRegistryView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _require_runtime_shared_token(request)
        queryset = (
            WorkspaceAgent.objects.filter(is_enabled=True)
            .select_related("profile", "source_template", "llm_version")
            .prefetch_related(
                Prefetch("skill_bindings", queryset=WorkspaceAgentSkillBinding.objects.select_related("skill").order_by("order", "created_at")),
                Prefetch(
                    "tool_bindings",
                    queryset=WorkspaceAgentToolBinding.objects.select_related("tool", "tool__tool_server").order_by("order", "created_at"),
                ),
            )
            .order_by("profile_id", "name")
        )
        serializer = WorkspaceAgentRuntimeInternalSerializer(queryset, many=True)
        return Response(
            {
                "agent_count": len(serializer.data),
                "agents": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
