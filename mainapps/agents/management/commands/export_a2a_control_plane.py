from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from mainapps.agents.models import WorkspaceAgent, WorkspaceToolConnection
from mainapps.profile.models import ProfileAgent


class Command(BaseCommand):
    help = "Export workspace AI settings and workspace agents for migration into the A2A service."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Absolute or relative path to write the migration JSON payload.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"]).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workspace_ai_settings = []
        for item in ProfileAgent.objects.select_related("profile", "version__llm").all().order_by("profile_id"):
            workspace_ai_settings.append(
                {
                    "profile": str(item.profile_id),
                    "name": item.name,
                    "version": item.version.model_name,
                    "provider": item.version.llm.provider,
                    "provider_label": item.version.llm.get_provider_display(),
                    "provider_base_url": item.version.llm.base_url or "",
                    "base_url": item.base_url or "",
                    "special_instruction": item.special_instruction or "",
                    "system_instruction": item.system_instruction or "",
                    "assistant_instruction": item.assistant_instruction or "",
                    "api_key": item.api_key or "",
                    "tavily_api_key": item.tavily_api_key or "",
                }
            )

        workspace_agents = []
        workspace_tool_connections = []
        queryset = (
            WorkspaceAgent.objects.select_related("profile", "source_template", "llm_version__llm", "created_by", "updated_by")
            .prefetch_related("skill_bindings__skill", "tool_bindings__tool")
            .all()
            .order_by("profile_id", "name")
        )
        for agent in queryset:
            workspace_agents.append(
                {
                    "profile": str(agent.profile_id),
                    "source_template_slug": agent.source_template.slug if agent.source_template_id else None,
                    "origin": agent.origin,
                    "visibility": agent.visibility,
                    "routing_policy": agent.routing_policy,
                    "slug": agent.slug,
                    "name": agent.name,
                    "description": agent.description,
                    "protocol_version": agent.protocol_version,
                    "preferred_transport": agent.preferred_transport,
                    "url": agent.url,
                    "provider_organization": agent.provider_organization,
                    "provider_url": agent.provider_url,
                    "version": agent.version,
                    "documentation_url": agent.documentation_url,
                    "icon_url": agent.icon_url,
                    "additional_interfaces": agent.additional_interfaces or [],
                    "capabilities": agent.capabilities or {},
                    "security_schemes": agent.security_schemes or {},
                    "security": agent.security or [],
                    "supports_authenticated_extended_card": agent.supports_authenticated_extended_card,
                    "default_input_modes": agent.default_input_modes or ["text"],
                    "default_output_modes": agent.default_output_modes or ["text"],
                    "system_instruction": agent.system_instruction or "",
                    "developer_instruction": agent.developer_instruction or "",
                    "assistant_instruction": agent.assistant_instruction or "",
                    "llm_version": (
                        {
                            "id": agent.llm_version.model_name,
                            "provider": agent.llm_version.llm.provider,
                            "provider_label": agent.llm_version.llm.get_provider_display(),
                            "model_name": agent.llm_version.model_name,
                            "base_url": agent.llm_version.llm.base_url,
                        }
                        if agent.llm_version_id
                        else None
                    ),
                    "llm_temperature": agent.llm_temperature,
                    "max_reasoning_steps": agent.max_reasoning_steps,
                    "metadata": agent.metadata or {},
                    "is_enabled": agent.is_enabled,
                    "template_version_snapshot": agent.template_version_snapshot or "",
                    "created_by": str(agent.created_by_id) if agent.created_by_id else None,
                    "updated_by": str(agent.updated_by_id) if agent.updated_by_id else None,
                    "skill_bindings": [
                        {
                            "skill_key": binding.skill.key,
                            "order": binding.order,
                            "is_primary": binding.is_primary,
                            "metadata": binding.metadata or {},
                        }
                        for binding in agent.skill_bindings.select_related("skill").all().order_by("order", "created_at")
                    ],
                    "tool_bindings": [
                        {
                            "tool_key": binding.tool.key,
                            "order": binding.order,
                            "is_required": binding.is_required,
                            "tool_config": binding.tool_config or {},
                        }
                        for binding in agent.tool_bindings.select_related("tool").all().order_by("order", "created_at")
                    ],
                }
            )

        for connection in (
            WorkspaceToolConnection.objects.select_related("profile", "tool_server", "owner_user", "created_by", "updated_by")
            .all()
            .order_by("profile_id", "name")
        ):
            workspace_tool_connections.append(
                {
                    "profile": str(connection.profile_id),
                    "tool_server_server_id": connection.tool_server.server_id,
                    "name": connection.name,
                    "slug": connection.slug,
                    "connection_scope": connection.connection_scope,
                    "owner_user": str(connection.owner_user_id) if connection.owner_user_id else None,
                    "auth_type": connection.auth_type or "",
                    "server_url_override": connection.server_url_override or "",
                    "credential_payload_encrypted": connection.credential_payload_encrypted or "",
                    "access_token_encrypted": connection.access_token_encrypted or "",
                    "refresh_token_encrypted": connection.refresh_token_encrypted or "",
                    "token_expires_at": connection.token_expires_at.isoformat() if connection.token_expires_at else None,
                    "granted_scopes": connection.granted_scopes or [],
                    "resource_owner_id": connection.resource_owner_id or "",
                    "resource_label": connection.resource_label or "",
                    "status": connection.status,
                    "last_tested_at": connection.last_tested_at.isoformat() if connection.last_tested_at else None,
                    "last_error": connection.last_error or "",
                    "metadata": connection.metadata or {},
                    "created_by": str(connection.created_by_id) if connection.created_by_id else None,
                    "updated_by": str(connection.updated_by_id) if connection.updated_by_id else None,
                }
            )

        payload = {
            "workspace_ai_settings": workspace_ai_settings,
            "workspace_agents": workspace_agents,
            "workspace_tool_connections": workspace_tool_connections,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(workspace_ai_settings)} workspace AI settings and "
                f"{len(workspace_agents)} workspace agents and "
                f"{len(workspace_tool_connections)} tool connections to {output_path}"
            )
        )
