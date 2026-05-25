from django.core.exceptions import ValidationError
from django.test import TestCase

from mainapps.agents.bootstrap import bootstrap_platform_catalog
from mainapps.accounts.models import User
from mainapps.agents.models import (
    AgentSkill,
    AgentTemplate,
    AgentTemplateSkillBinding,
    AgentTemplateToolBinding,
    AgentTool,
    ScopeChoices,
    ToolConnectionScopeChoices,
    ToolServer,
    WorkspaceAgent,
    WorkspaceAgentToolBinding,
    WorkspaceToolConnection,
)
from mainapps.profile.models import CompanyProfile


class AgentControlPlaneModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="owner@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.user,
            name="Acme Health",
        )

    def test_tool_full_name_uses_server_prefix(self):
        server = ToolServer.objects.create(
            scope=ScopeChoices.PLATFORM,
            server_id="users",
            name="Users",
            tool_name_prefix="users.",
        )
        tool = AgentTool.objects.create(
            scope=ScopeChoices.PLATFORM,
            key="users.search_company_staff",
            display_name="Search Company Staff",
            remote_tool_name="search_company_staff",
            tool_server=server,
        )

        self.assertEqual(tool.full_tool_name, "users.search_company_staff")

    def test_workspace_agent_requires_template_when_origin_is_template(self):
        agent = WorkspaceAgent(
            profile=self.profile,
            slug="inventory-helper",
            name="Inventory Helper",
            origin="template",
        )

        with self.assertRaises(ValidationError):
            agent.full_clean()

    def test_agent_template_builds_a2a_payload_with_skills_and_tools(self):
        template = AgentTemplate.objects.create(
            slug="users",
            name="Users",
            description="Workspace access specialist.",
            preferred_transport="kafka",
        )
        skill = AgentSkill.objects.create(
            scope=ScopeChoices.PLATFORM,
            key="workspace_membership_visibility",
            name="Workspace Membership Visibility",
            description="Inspect memberships.",
            tags=["users", "workspace"],
            examples=["Show accessible workspaces."],
        )
        server = ToolServer.objects.create(
            scope=ScopeChoices.PLATFORM,
            server_id="users",
            name="Users",
            tool_name_prefix="users.",
        )
        tool = AgentTool.objects.create(
            scope=ScopeChoices.PLATFORM,
            key="users.list_accessible_company_profiles",
            display_name="List Accessible Company Profiles",
            remote_tool_name="list_accessible_company_profiles",
            tool_server=server,
            description="List workspaces the caller can access.",
        )
        AgentTemplateSkillBinding.objects.create(template=template, skill=skill, order=0, is_primary=True)
        AgentTemplateToolBinding.objects.create(template=template, tool=tool, order=0, is_required=True)

        payload = template.build_agent_card_payload()

        self.assertEqual(payload["name"], "users")
        self.assertEqual(payload["preferredTransport"], "kafka")
        self.assertEqual(payload["skills"][0]["id"], "workspace_membership_visibility")
        self.assertEqual(payload["metadata"]["tools"][0]["name"], "users.list_accessible_company_profiles")
        self.assertTrue(payload["metadata"]["tools"][0]["required"])

    def test_workspace_agent_payload_uses_bound_workspace_tools(self):
        server = ToolServer.objects.create(
            scope=ScopeChoices.PLATFORM,
            server_id="inventory",
            name="Inventory",
            tool_name_prefix="inventory.",
        )
        tool = AgentTool.objects.create(
            scope=ScopeChoices.PLATFORM,
            key="inventory.search_inventory_items",
            display_name="Search Inventory Items",
            remote_tool_name="search_inventory_items",
            tool_server=server,
        )
        agent = WorkspaceAgent.objects.create(
            profile=self.profile,
            slug="my-inventory-helper",
            name="My Inventory Helper",
            description="Custom workspace agent.",
            origin="custom",
            created_by=self.user,
        )
        WorkspaceAgentToolBinding.objects.create(agent=agent, tool=tool, order=0, is_required=False)

        payload = agent.build_agent_card_payload()

        self.assertEqual(payload["name"], "my-inventory-helper")
        self.assertEqual(payload["metadata"]["tools"][0]["name"], "inventory.search_inventory_items")

    def test_workspace_agent_runtime_payload_uses_internal_runtime_name(self):
        agent = WorkspaceAgent.objects.create(
            profile=self.profile,
            slug="host",
            name="Host",
            description="Workspace host agent.",
            origin="custom",
            created_by=self.user,
        )

        runtime_payload = agent.build_runtime_card_payload()

        self.assertNotEqual(runtime_payload["name"], "host")
        self.assertEqual(runtime_payload["metadata"]["ka2aRuntime"]["publicSlug"], "host")
        self.assertEqual(runtime_payload["metadata"]["ka2aRuntime"]["profileId"], self.profile.id)
        self.assertEqual(runtime_payload["metadata"]["ka2aRuntime"]["workspaceAgentId"], str(agent.id))

    def test_user_scoped_tool_connection_requires_owner_user(self):
        server = ToolServer.objects.create(
            scope=ScopeChoices.PLATFORM,
            server_id="shopify",
            name="Shopify",
        )
        connection = WorkspaceToolConnection(
            profile=self.profile,
            tool_server=server,
            name="Shopify Owner Connection",
            slug="shopify-owner",
            connection_scope=ToolConnectionScopeChoices.USER,
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_workspace_scoped_tool_connection_rejects_owner_user(self):
        server = ToolServer.objects.create(
            scope=ScopeChoices.PLATFORM,
            server_id="shopify",
            name="Shopify",
        )
        connection = WorkspaceToolConnection(
            profile=self.profile,
            tool_server=server,
            name="Shopify Workspace Connection",
            slug="shopify-workspace",
            connection_scope=ToolConnectionScopeChoices.WORKSPACE,
            owner_user=self.user,
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_bootstrap_seeds_external_mcp_tool_servers(self):
        bootstrap_platform_catalog()

        shopify_server = ToolServer.objects.get(scope=ScopeChoices.PLATFORM, server_id="shopify_admin")
        google_server = ToolServer.objects.get(scope=ScopeChoices.PLATFORM, server_id="google_workspace")

        self.assertEqual(shopify_server.transport, "mcp")
        self.assertEqual(shopify_server.auth_mode, "custom")
        self.assertEqual(shopify_server.metadata.get("catalogType"), "external_mcp")
        self.assertIn("supportedAuthTypes", shopify_server.auth_config)

        self.assertEqual(google_server.auth_mode, "service_account")
        self.assertEqual(google_server.metadata.get("provider"), "Google")
