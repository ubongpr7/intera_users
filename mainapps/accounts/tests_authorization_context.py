from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mainapps.accounts.models import User
from mainapps.accounts.serializers import MyTokenObtainPairSerializer
from mainapps.permit.models import PlatformChoices
from mainapps.profile.models import CompanyProfile

from .authorization_context import (
    access_context_hash,
    issue_authorization_context,
    issue_websocket_ticket,
    public_signing_jwks,
)


_jwks_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_jwks_private_pem = _jwks_private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
_jwks_public_pem = _jwks_private_key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)


class AuthorizationContextTests(SimpleTestCase):
    def test_context_hash_is_stable_for_same_identity(self):
        self.assertEqual(
            access_context_hash(user_id=1, profile_id=2, session_version=3),
            access_context_hash(user_id=1, profile_id=2, session_version=3),
        )

    def test_context_hash_is_platform_bound(self):
        self.assertNotEqual(
            access_context_hash(user_id=1, profile_id=2, session_version=3, platform="intera_ims"),
            access_context_hash(user_id=1, profile_id=2, session_version=3, platform="hosperator"),
        )

    def test_context_hash_is_access_token_bound(self):
        self.assertNotEqual(
            access_context_hash(
                user_id=1,
                profile_id=2,
                session_version=3,
                platform="hosperator",
                access_token_id="access-a",
            ),
            access_context_hash(
                user_id=1,
                profile_id=2,
                session_version=3,
                platform="hosperator",
                access_token_id="access-b",
            ),
        )

    def test_websocket_ticket_preserves_platform(self):
        import jwt
        from django.conf import settings

        ticket = issue_websocket_ticket({
            "user_id": "1",
            "profile_id": "2",
            "platform": "hosperator",
            "access_context_hash": "hash",
        })
        algorithm = settings.SIMPLE_JWT["ALGORITHM"]
        verifying_key = settings.SIMPLE_JWT.get("VERIFYING_KEY") or settings.SECRET_KEY
        payload = jwt.decode(ticket, verifying_key, algorithms=[algorithm], options={"verify_aud": False})
        self.assertEqual(payload["platform"], "hosperator")

    def test_websocket_ticket_preserves_pair_binding(self):
        import jwt
        from django.conf import settings

        ticket = issue_websocket_ticket({
            "jti": "context-jti",
            "user_id": "1",
            "profile_id": "2",
            "platform": "hosperator",
            "session_version": 4,
            "access_token_id": "access-jti",
            "access_context_hash": "hash",
        })
        algorithm = settings.SIMPLE_JWT["ALGORITHM"]
        verifying_key = settings.SIMPLE_JWT.get("VERIFYING_KEY") or settings.SECRET_KEY
        payload = jwt.decode(ticket, verifying_key, algorithms=[algorithm], options={"verify_aud": False})
        self.assertEqual(payload["authorization_context_jti"], "context-jti")
        self.assertEqual(payload["access_token_id"], "access-jti")
        self.assertEqual(payload["session_version"], 4)

    def test_websocket_ticket_omits_legacy_permission_claims(self):
        import jwt
        from django.conf import settings

        payload = {
            "wildcards": ["system:cashier"],
            "wildcard_permissions": {"system:cashier": ["read_pos", "operate_pos"]},
            "permissions": ["read_pos"],
        }
        ticket = issue_websocket_ticket(payload)
        algorithm = settings.SIMPLE_JWT["ALGORITHM"]
        verifying_key = settings.SIMPLE_JWT.get("VERIFYING_KEY") or settings.SECRET_KEY
        decoded = jwt.decode(ticket, verifying_key, algorithms=[algorithm], options={"verify_aud": False})
        self.assertNotIn("permissions", decoded)
        self.assertNotIn("wildcards", decoded)
        self.assertNotIn("wildcard_permissions", decoded)

    @override_settings(
        SIMPLE_JWT={
            **settings.SIMPLE_JWT,
            "ALGORITHM": "RS256",
            "SIGNING_KEY": _jwks_private_pem,
            "VERIFYING_KEY": _jwks_public_pem,
        },
        JWT_SIGNING_KEY_ID="users-key-1",
    )
    def test_public_signing_jwks_exposes_only_rsa_verification_material(self):
        payload = public_signing_jwks()
        self.assertEqual(len(payload["keys"]), 1)
        key = payload["keys"][0]
        self.assertEqual(key["kid"], "users-key-1")
        self.assertEqual(key["use"], "sig")
        self.assertEqual(key["alg"], "RS256")
        self.assertEqual(key["kty"], "RSA")
        self.assertNotIn("d", key)


class WebSocketTicketApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="websocket-ticket@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(owner=self.user, name="Ticket Hospital")
        _refresh, self.access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            self.user,
            self.profile,
            platform=PlatformChoices.HOSPERATOR,
        )
        self.context = issue_authorization_context(
            self.user,
            profile=self.profile,
            platform=PlatformChoices.HOSPERATOR,
            access_token_id=self.access.get("jti"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user, token=self.access)

    def test_ticket_response_has_documented_shape_and_compatibility_alias(self):
        response = self.client.post(
            reverse("websocket-ticket"),
            {},
            format="json",
            HTTP_X_INTERA_AUTHORIZATION_CONTEXT=self.context,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["ws_ticket"], response.json()["ticket"])
        self.assertGreater(response.json()["expires_in"], 0)

    def test_ticket_rejects_context_bound_to_another_access_token(self):
        _refresh, other_access = MyTokenObtainPairSerializer.issue_tokens_for_profile(
            self.user,
            self.profile,
            platform=PlatformChoices.HOSPERATOR,
        )
        self.client.force_authenticate(user=self.user, token=other_access)

        response = self.client.post(
            reverse("websocket-ticket"),
            {},
            format="json",
            HTTP_X_INTERA_AUTHORIZATION_CONTEXT=self.context,
        )

        self.assertEqual(response.status_code, 401)
