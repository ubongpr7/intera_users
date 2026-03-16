import asyncio
import os
from unittest.mock import patch

from django.test import SimpleTestCase
from starlette.testclient import TestClient

from mainapps.accounts.models import User
from mainapps.profile.models import CompanyProfile
from mcp_server.server import (
    _build_principal_from_token,
    _build_transport_security_settings,
    _company_profile_payload,
    _extract_bearer_token,
    _principal_var,
    app as users_mcp_app,
    search_company_staff,
)


class UsersMcpAuthTests(SimpleTestCase):
    def test_extract_bearer_token_requires_bearer_scheme(self):
        self.assertEqual(_extract_bearer_token("Bearer token-123"), "token-123")
        self.assertIsNone(_extract_bearer_token("Basic token-123"))
        self.assertIsNone(_extract_bearer_token("Bearer "))

    @patch("mcp_server.server.UntypedToken")
    def test_build_principal_from_token_reads_claims(self, token_cls):
        token_cls.return_value.payload = {
            "user_id": 42,
            "profile_id": 9,
            "company_code": "ACME",
            "permissions": ["manage_staff"],
        }

        principal = _build_principal_from_token("jwt-token")

        self.assertEqual(principal.user_id, "42")
        self.assertEqual(principal.profile_id, 9)
        self.assertEqual(principal.company_code, "ACME")
        self.assertEqual(principal.permissions, {"manage_staff"})

    @patch.dict(
        os.environ,
        {
            "ALLOWED_HOSTS": "users.mcp.interaims.com,users.interaims.com",
            "CORS_ALLOWED_ORIGINS": "http://localhost:3000,https://dev.interaims.com",
        },
        clear=False,
    )
    def test_transport_security_uses_configured_hosts(self):
        settings = _build_transport_security_settings()

        self.assertIn("users.mcp.interaims.com", settings.allowed_hosts)
        self.assertIn("users.interaims.com", settings.allowed_hosts)
        self.assertIn("http://localhost:3000", settings.allowed_origins)


class UsersMcpSerializationTests(SimpleTestCase):
    def test_company_profile_payload_includes_workspace_summary(self):
        owner = User(id=7, email="owner@example.com")
        profile = CompanyProfile(
            id=3,
            owner=owner,
            owner_id=owner.id,
            company_code="ACME1",
            name="Acme Retail",
            email="hello@example.com",
            phone="+2347000000000",
            is_verified=True,
        )
        setattr(profile, "active_member_count", 5)
        setattr(profile, "active_role_count", 2)
        setattr(profile, "active_group_count", 1)
        setattr(profile, "active_memberships_for_mcp", [])
        setattr(profile, "agent", object())

        payload = _company_profile_payload(profile, principal_user_id=owner.id)

        self.assertEqual(payload["name"], "Acme Retail")
        self.assertTrue(payload["is_owner"])
        self.assertEqual(payload["member_count"], 5)
        self.assertTrue(payload["agent_configured"])


class UsersMcpToolTests(SimpleTestCase):
    def test_search_company_staff_requires_authenticated_context(self):
        token = _principal_var.set(None)
        try:
            with self.assertRaises(RuntimeError):
                asyncio.run(search_company_staff(query="john"))
        finally:
            _principal_var.reset(token)


class UsersMcpAppTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mcp_client_ctx = TestClient(users_mcp_app, base_url="http://127.0.0.1:8000")
        cls.mcp_client = cls.mcp_client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.mcp_client_ctx.__exit__(None, None, None)
        super().tearDownClass()

    def test_health_endpoint_is_available(self):
        response = self.mcp_client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_mcp_mount_initializes_without_server_error(self):
        redirect = self.mcp_client.get("/mcp", follow_redirects=False)
        response = self.mcp_client.get("/mcp/", headers={"accept": "application/json"})

        self.assertEqual(redirect.status_code, 307)
        self.assertEqual(redirect.headers["location"], "http://127.0.0.1:8000/mcp/")
        self.assertEqual(response.status_code, 406)
