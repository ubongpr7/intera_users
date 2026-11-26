import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import TestCase, SimpleTestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from mainapps.accounts.models import User
from mainapps.accounts.views import (
    McpConnectApproveView,
    McpConnectStartView,
    McpConnectTokenView,
    McpConnectRefreshView,
    McpConnectWorkspacesView,
)
from mainapps.permit.models import CustomUserPermission, PermissionCategory, PlatformChoices
from mainapps.profile.models import CompanyMembership, CompanyProfile


class McpConnectUtilityTests(SimpleTestCase):
    def test_start_requires_loopback_callback_and_s256_challenge(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/auth/mcp/connect/start/",
            {"redirect_uri": "https://evil.example/callback", "code_challenge": "x" * 43},
            format="json",
        )

        response = McpConnectStartView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_token_exchange_rejects_unknown_code(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/auth/mcp/connect/token/",
            {"code": "not-a-real-code", "code_verifier": secrets.token_urlsafe(32)},
            format="json",
        )

        response = McpConnectTokenView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_mcp_refresh_rejects_unknown_token(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/auth/mcp/connect/refresh/",
            {"refresh_token": "not-a-real-token"},
            format="json",
        )

        response = McpConnectRefreshView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_start_preserves_preferred_workspace_for_browser_selection(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/auth/mcp/connect/start/",
            {
                "client_id": "intera-cli",
                "redirect_uri": "http://127.0.0.1:49152/callback",
                "code_challenge": "x" * 43,
                "preferred_profile_id": "17",
            },
            format="json",
        )

        response = McpConnectStartView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertIn("profile_id=17", response.data["frontend_url"])


class McpConnectWorkspaceTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(email="mcp-owner@example.com", password="password123")
        self.profile = CompanyProfile.objects.create(owner=self.user, name="MCP Workspace")
        self.request_id = "mcp-request-test"
        cache.set(
            f"mcp-connect-request:{self.request_id}",
            {
                "state": "state-test",
                "client_id": "intera-cli",
                "redirect_uri": "http://127.0.0.1:49152/callback",
                "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(b"verifier").digest()).rstrip(b"=").decode(),
            },
            600,
        )

    def tearDown(self):
        cache.delete(f"mcp-connect-request:{self.request_id}")

    def test_owner_can_list_and_approve_workspace(self):
        self.client.force_authenticate(user=self.user)
        workspaces_response = self.client.get(
            f"/auth/mcp/connect/workspaces/?request_id={self.request_id}"
        )

        self.assertEqual(workspaces_response.status_code, 200)
        workspace = next(
            item for item in workspaces_response.data["workspaces"] if item["id"] == str(self.profile.id)
        )
        self.assertTrue(workspace["can_use_agent"])

        approve_response = self.client.post(
            "/auth/mcp/connect/approve/",
            {"request_id": self.request_id, "profile_id": str(self.profile.id)},
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
        )

        self.assertEqual(approve_response.status_code, 200)
        self.assertIn("code=", approve_response.data["redirect_uri"])

    def test_member_without_agent_grant_can_see_workspace_but_cannot_approve(self):
        member = User.objects.create_user(email="mcp-member@example.com", password="password123")
        CompanyMembership.objects.create(
            user=member,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
        )
        self.client.force_authenticate(user=member)

        workspaces_response = self.client.get(
            f"/auth/mcp/connect/workspaces/?request_id={self.request_id}"
        )

        self.assertEqual(workspaces_response.status_code, 200)
        workspace = next(
            item for item in workspaces_response.data["workspaces"] if item["id"] == str(self.profile.id)
        )
        self.assertFalse(workspace["can_use_agent"])

        approve_response = self.client.post(
            "/auth/mcp/connect/approve/",
            {"request_id": self.request_id, "profile_id": str(self.profile.id)},
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
        )

        self.assertEqual(approve_response.status_code, 403)
        self.assertEqual(approve_response.data["permission"], "interact_with_agent")

    def test_exchange_uses_short_lived_cli_tokens_and_refresh_rotation(self):
        self.client.force_authenticate(user=self.user)
        approve_response = self.client.post(
            "/auth/mcp/connect/approve/",
            {"request_id": self.request_id, "profile_id": str(self.profile.id)},
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(approve_response.status_code, 200)
        code = parse_qs(urlparse(approve_response.data["redirect_uri"]).query)["code"][0]

        token_response = self.client.post(
            "/auth/mcp/connect/token/",
            {
                "code": code,
                "code_verifier": "verifier",
                "client_id": "intera-cli",
                "redirect_uri": "http://127.0.0.1:49152/callback",
            },
            format="json",
        )

        self.assertEqual(token_response.status_code, 200)
        access = AccessToken(token_response.data["access_token"])
        refresh = RefreshToken(token_response.data["refresh_token"])
        self.assertEqual(access["client_id"], "intera-cli")
        self.assertEqual(refresh["client_id"], "intera-cli")
        self.assertLessEqual(access["exp"] - access["iat"], 900)

        rotated = self.client.post(
            "/auth/mcp/connect/refresh/",
            {"refresh_token": token_response.data["refresh_token"]},
            format="json",
        )

        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.data["refresh_token"], token_response.data["refresh_token"])
        with self.assertRaises(TokenError):
            refresh.check_blacklist()

    def test_refresh_rechecks_agent_grant_after_it_is_revoked(self):
        member = User.objects.create_user(email="mcp-revoked@example.com", password="password123")
        membership = CompanyMembership.objects.create(
            user=member,
            profile=self.profile,
            role=CompanyMembership.MembershipRole.MEMBER,
            is_active=True,
        )
        category = PermissionCategory.objects.create(
            platform=PlatformChoices.INTERA_IMS,
            name="MCP Connect Tests",
        )
        permission = CustomUserPermission.objects.create(
            platform=PlatformChoices.INTERA_IMS,
            codename="interact_with_agent",
            category=category,
        )
        membership.custom_permissions.add(permission)
        self.client.force_authenticate(user=member)

        approve_response = self.client.post(
            "/auth/mcp/connect/approve/",
            {"request_id": self.request_id, "profile_id": str(self.profile.id)},
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(approve_response.status_code, 200)
        code = parse_qs(urlparse(approve_response.data["redirect_uri"]).query)["code"][0]
        token_response = self.client.post(
            "/auth/mcp/connect/token/",
            {
                "code": code,
                "code_verifier": "verifier",
                "client_id": "intera-cli",
                "redirect_uri": "http://127.0.0.1:49152/callback",
            },
            format="json",
        )
        self.assertEqual(token_response.status_code, 200)

        membership.custom_permissions.remove(permission)
        refresh_response = self.client.post(
            "/auth/mcp/connect/refresh/",
            {"refresh_token": token_response.data["refresh_token"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, 403)
        self.assertIn("Agent access is no longer available", refresh_response.data["detail"])
