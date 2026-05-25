from __future__ import annotations

import json
from pathlib import Path

from django.db import transaction
from .models import (
    AgentInstructionPreset,
    AgentSkill,
    AgentTemplate,
    AgentTemplateSkillBinding,
    AgentTemplateToolBinding,
    AgentTool,
    ScopeChoices,
    ToolAuthModeChoices,
    ToolServer,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
KA2A_ROOT = REPO_ROOT / "kafka_a2a"
AGENT_CARD_DIR = KA2A_ROOT / "agent_cards"
PROMPT_DIR = KA2A_ROOT / "prompts"
MCP_CONFIG_PATH = KA2A_ROOT / "mcp-tools.prod.json"


_EXTERNAL_TOOL_SERVERS: tuple[dict[str, object], ...] = (
    {
        "id": "shopify_admin",
        "name": "Shopify Admin MCP",
        "description": (
            "Merchant-side Shopify MCP connection for catalog, inventory, orders, and fulfillment workflows. "
            "Use your own hosted MCP endpoint or a trusted provider endpoint."
        ),
        "transport": "mcp",
        "serverUrl": "",
        "toolNamePrefix": "shopify.",
        "auth": {
            "mode": ToolAuthModeChoices.CUSTOM,
            "recommendedAuthType": "custom",
            "supportedAuthTypes": ["oauth_workspace", "api_key_header", "custom"],
            "notes": [
                "Shopify merchant-admin integrations usually need OAuth or an Admin API token.",
                "Use Server URL Override if your MCP endpoint is tenant-specific.",
            ],
            "credentialExample": {
                "store_domain": "demo-store.myshopify.com",
                "header_name": "X-Shopify-Access-Token",
                "api_key": "shpat_xxx",
            },
        },
        "metadata": {
            "catalogType": "external_mcp",
            "category": "commerce",
            "provider": "Shopify",
            "documentationLabel": "Shopify merchant MCP via your hosted endpoint",
            "connectionGuide": [
                "Choose this server when you want an agent to read or update Shopify merchant data.",
                "Save the store token in Credential Payload JSON or use OAuth Workspace when available.",
                "Set Server URL Override to the actual MCP endpoint if the default catalog entry is blank.",
            ],
            "suggestedCapabilities": [
                "import_products",
                "sync_inventory_levels",
                "pull_orders",
                "push_fulfillment_status",
            ],
        },
    },
    {
        "id": "notion",
        "name": "Notion MCP",
        "description": "External Notion MCP connection for workspace docs, databases, and knowledge search.",
        "transport": "mcp",
        "serverUrl": "",
        "toolNamePrefix": "notion.",
        "auth": {
            "mode": ToolAuthModeChoices.CUSTOM,
            "recommendedAuthType": "oauth_workspace",
            "supportedAuthTypes": ["oauth_workspace", "api_key_header", "custom"],
            "credentialExample": {
                "header_name": "Authorization",
                "token": "secret_xxx",
            },
        },
        "metadata": {
            "catalogType": "external_mcp",
            "category": "knowledge",
            "provider": "Notion",
            "connectionGuide": [
                "Use this for knowledge-base lookup, page updates, or database automation.",
                "Most hosted Notion MCP setups are OAuth-oriented.",
            ],
            "suggestedCapabilities": ["search_docs", "update_pages", "query_databases"],
        },
    },
    {
        "id": "slack",
        "name": "Slack MCP",
        "description": "External Slack MCP connection for channels, threads, approvals, and notifications.",
        "transport": "mcp",
        "serverUrl": "",
        "toolNamePrefix": "slack.",
        "auth": {
            "mode": ToolAuthModeChoices.CUSTOM,
            "recommendedAuthType": "oauth_workspace",
            "supportedAuthTypes": ["oauth_workspace", "custom"],
            "credentialExample": {
                "workspace_id": "T123456",
                "bot_token": "xoxb-xxx",
            },
        },
        "metadata": {
            "catalogType": "external_mcp",
            "category": "collaboration",
            "provider": "Slack",
            "connectionGuide": [
                "Use this for notification agents, escalation flows, or channel summaries.",
                "Slack MCP setups are usually app-backed and OAuth-based.",
            ],
            "suggestedCapabilities": ["post_messages", "read_threads", "list_channels"],
        },
    },
    {
        "id": "github",
        "name": "GitHub MCP",
        "description": "External GitHub MCP connection for repositories, issues, pull requests, and code search.",
        "transport": "mcp",
        "serverUrl": "",
        "toolNamePrefix": "github.",
        "auth": {
            "mode": ToolAuthModeChoices.CUSTOM,
            "recommendedAuthType": "api_key_header",
            "supportedAuthTypes": ["api_key_header", "oauth_workspace", "custom"],
            "credentialExample": {
                "header_name": "Authorization",
                "token": "ghp_xxx",
            },
        },
        "metadata": {
            "catalogType": "external_mcp",
            "category": "engineering",
            "provider": "GitHub",
            "connectionGuide": [
                "Use this for repository-aware engineering or issue triage agents.",
                "A personal access token is the simplest first pass.",
            ],
            "suggestedCapabilities": ["read_repos", "search_code", "manage_issues", "review_prs"],
        },
    },
    {
        "id": "google_workspace",
        "name": "Google Workspace MCP",
        "description": "External Google Workspace MCP connection for Drive, Gmail, Calendar, and docs-oriented flows.",
        "transport": "mcp",
        "serverUrl": "",
        "toolNamePrefix": "google.",
        "auth": {
            "mode": ToolAuthModeChoices.SERVICE_ACCOUNT,
            "recommendedAuthType": "service_account",
            "supportedAuthTypes": ["oauth_workspace", "service_account", "custom"],
            "credentialExample": {
                "project_id": "your-gcp-project",
                "client_email": "service-account@project.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
            },
        },
        "metadata": {
            "catalogType": "external_mcp",
            "category": "workspace",
            "provider": "Google",
            "connectionGuide": [
                "Use service-account mode for server-to-server access where supported.",
                "Use OAuth Workspace when the MCP provider expects per-user authorization.",
            ],
            "suggestedCapabilities": ["search_drive", "read_mail", "calendar_lookup"],
        },
    },
)


_TEMPLATE_RUNTIME_METADATA: dict[str, dict[str, object]] = {
    "host": {
        "processor": "langgraph-chat",
        "tool_executor": "kafka_a2a.local_tools:build_interaction_tool_executor",
        "allowed_downstream_slugs": ["onboarding", "users", "product", "inventory", "pos"],
    },
    "onboarding": {
        "processor": "langgraph-chat",
        "tool_executor": "kafka_a2a.local_tools:build_interaction_tool_executor",
        "allowed_downstream_slugs": ["users", "product", "inventory"],
    },
    "product": {
        "processor": "langgraph-chat",
        "tool_executor": "kafka_a2a.local_tools:build_interaction_tool_executor",
        "allowed_downstream_slugs": [
            "product_discovery",
            "product_catalog_admin",
            "product_merchandising",
            "product_pricing",
        ],
    },
    "inventory": {
        "processor": "langgraph-chat",
        "tool_executor": "kafka_a2a.local_tools:build_interaction_tool_executor",
        "allowed_downstream_slugs": [
            "inventory_visibility",
            "inventory_setup",
            "inventory_procurement",
            "inventory_fulfillment",
        ],
    },
    "pos": {
        "processor": "langgraph-chat",
        "tool_executor": "kafka_a2a.local_tools:build_interaction_tool_executor",
        "allowed_downstream_slugs": ["pos_live", "pos_admin"],
    },
}


def _humanize_identifier(value: str) -> str:
    return value.replace(".", " ").replace("_", " ").strip().title()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _auth_mode_from_value(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    valid_values = {choice for choice, _ in ToolAuthModeChoices.choices}
    return normalized if normalized in valid_values else ToolAuthModeChoices.NONE


def _prompt_path_for_agent(slug: str) -> Path:
    return PROMPT_DIR / f"{slug}_agent.txt"


@transaction.atomic
def bootstrap_platform_catalog(*, stdout=None) -> dict[str, int]:
    stats = {
        "tool_servers": 0,
        "tools": 0,
        "skills": 0,
        "instruction_presets": 0,
        "templates": 0,
        "template_skill_bindings": 0,
        "template_tool_bindings": 0,
    }

    config = _load_json(MCP_CONFIG_PATH)
    server_map: dict[str, ToolServer] = {}

    server_catalog = list(config.get("sharedServers") or [])
    server_catalog.extend(_EXTERNAL_TOOL_SERVERS)

    for server_data in server_catalog:
        server_id = server_data["id"]
        server, created = ToolServer.objects.update_or_create(
            scope=ScopeChoices.PLATFORM,
            server_id=server_id,
            defaults={
                "name": str(server_data.get("name") or _humanize_identifier(server_id)),
                "description": str(server_data.get("description") or f"MCP server for {server_id} tools."),
                "transport": str(server_data.get("transport") or "mcp"),
                "server_url": server_data.get("serverUrl", ""),
                "tool_name_prefix": server_data.get("toolNamePrefix", ""),
                "auth_mode": _auth_mode_from_value((server_data.get("auth") or {}).get("mode")),
                "auth_config": server_data.get("auth") or {},
                "metadata": server_data.get("metadata") or server_data,
                "last_synced_at": None,
                "is_active": True,
            },
        )
        server_map[server_id] = server
        stats["tool_servers"] += 1 if created else 0

    card_paths = sorted(AGENT_CARD_DIR.glob("*.agent-card.json"))
    template_map: dict[str, AgentTemplate] = {}

    for card_path in card_paths:
        card = _load_json(card_path)
        slug = card["name"]
        prompt_path = _prompt_path_for_agent(slug)
        prompt_text = _load_text(prompt_path) if prompt_path.exists() else ""

        template, created = AgentTemplate.objects.update_or_create(
            slug=slug,
            defaults={
                "name": _humanize_identifier(slug),
                "description": card.get("description", ""),
                "protocol_version": card.get("protocolVersion", "0.3.0"),
                "url": card.get("url", ""),
                "preferred_transport": card.get("preferredTransport", "kafka"),
                "version": card.get("version", "0.1.0"),
                "capabilities": card.get("capabilities") or {},
                "default_input_modes": card.get("defaultInputModes") or ["text"],
                "default_output_modes": card.get("defaultOutputModes") or ["text"],
                "system_instruction": prompt_text,
                "metadata": {
                    "seededFrom": str(card_path.relative_to(REPO_ROOT)),
                    "runtime": {
                        "processor": "langgraph-chat",
                        **_TEMPLATE_RUNTIME_METADATA.get(slug, {}),
                    },
                },
                "is_active": True,
                "is_featured": slug in {"host", "onboarding", "users", "product", "inventory", "pos"},
                "allow_workspace_installs": True,
            },
        )
        template_map[slug] = template
        stats["templates"] += 1 if created else 0

        preset, preset_created = AgentInstructionPreset.objects.update_or_create(
            scope=ScopeChoices.PLATFORM,
            key=f"{slug}.system",
            defaults={
                "title": f"{_humanize_identifier(slug)} System Instruction",
                "description": card.get("description", ""),
                "instruction_type": "system",
                "body": prompt_text,
                "tags": [slug],
                "metadata": {"seededFrom": str(prompt_path.relative_to(REPO_ROOT)) if prompt_path.exists() else None},
                "is_default": slug in {"host", "onboarding", "users", "product", "inventory", "pos"},
                "is_active": True,
            },
        )
        stats["instruction_presets"] += 1 if preset_created else 0

        AgentTemplateSkillBinding.objects.filter(template=template).exclude(
            skill__key__in=[skill["id"] for skill in card.get("skills") or []]
        ).delete()

        for order, skill_data in enumerate(card.get("skills") or []):
            skill, skill_created = AgentSkill.objects.update_or_create(
                scope=ScopeChoices.PLATFORM,
                key=skill_data["id"],
                defaults={
                    "name": skill_data.get("name") or _humanize_identifier(skill_data["id"]),
                    "description": skill_data.get("description", ""),
                    "tags": skill_data.get("tags") or [],
                    "examples": skill_data.get("examples") or [],
                    "input_modes": skill_data.get("inputModes") or ["text"],
                    "output_modes": skill_data.get("outputModes") or ["text"],
                    "metadata": {"seededFrom": str(card_path.relative_to(REPO_ROOT))},
                    "is_active": True,
                },
            )
            stats["skills"] += 1 if skill_created else 0
            _, binding_created = AgentTemplateSkillBinding.objects.update_or_create(
                template=template,
                skill=skill,
                defaults={
                    "order": order,
                    "is_primary": order == 0,
                    "metadata": {},
                },
            )
            stats["template_skill_bindings"] += 1 if binding_created else 0

    for agent_name, agent_data in (config.get("agents") or {}).items():
        template = template_map.get(agent_name)
        if template is None:
            continue
        bound_tool_keys: list[str] = []
        tool_order = 0
        for server_data in agent_data.get("servers") or []:
            server = server_map.get(server_data.get("ref", ""))
            if server is None:
                continue
            for tool_name in server_data.get("tools") or []:
                tool_key = f"{server.server_id}.{tool_name}"
                bound_tool_keys.append(tool_key)
                tool, tool_created = AgentTool.objects.update_or_create(
                    scope=ScopeChoices.PLATFORM,
                    key=tool_key,
                    defaults={
                        "display_name": _humanize_identifier(tool_name),
                        "description": "",
                        "tool_server": server,
                        "remote_tool_name": tool_name,
                        "auth_mode": server.auth_mode,
                        "metadata": {"serverRef": server.server_id, "seededFrom": "mcp-tools.prod.json"},
                        "is_discoverable": True,
                        "is_active": True,
                    },
                )
                stats["tools"] += 1 if tool_created else 0
                _, binding_created = AgentTemplateToolBinding.objects.update_or_create(
                    template=template,
                    tool=tool,
                    defaults={
                        "order": tool_order,
                        "is_required": False,
                        "tool_config": {},
                    },
                )
                stats["template_tool_bindings"] += 1 if binding_created else 0
                tool_order += 1
        AgentTemplateToolBinding.objects.filter(template=template).exclude(tool__key__in=bound_tool_keys).delete()

    if stdout is not None:
        stdout.write("Bootstrapped agent control-plane catalog from kafka_a2a assets.")

    return stats
