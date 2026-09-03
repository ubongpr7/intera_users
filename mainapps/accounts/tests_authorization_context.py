from django.test import SimpleTestCase

from .authorization_context import access_context_hash, has_context_permission, issue_websocket_ticket


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

    def test_wildcard_permission_mapping_grants_only_mapped_permission(self):
        payload = {
            "wildcards": ["system:cashier"],
            "wildcard_permissions": {"system:cashier": ["read_pos", "operate_pos"]},
            "permissions": [],
        }
        self.assertTrue(has_context_permission(payload, "operate_pos"))
        self.assertFalse(has_context_permission(payload, "manage_pos_settings"))

    def test_scoped_wildcard_permission_matches_platform_permission(self):
        payload = {
            "wildcards": ["system:workspace-owner"],
            "wildcard_permissions": {"system:workspace-owner": ["hosperator.*"]},
            "permissions": [],
        }
        self.assertTrue(has_context_permission(payload, "hosperator.patient.read"))
        self.assertFalse(has_context_permission(payload, "read_inventory"))
