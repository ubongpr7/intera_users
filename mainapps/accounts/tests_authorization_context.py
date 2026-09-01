from django.test import SimpleTestCase

from .authorization_context import access_context_hash, has_context_permission


class AuthorizationContextTests(SimpleTestCase):
    def test_context_hash_is_stable_for_same_identity(self):
        self.assertEqual(
            access_context_hash(user_id=1, profile_id=2, session_version=3),
            access_context_hash(user_id=1, profile_id=2, session_version=3),
        )

    def test_wildcard_permission_mapping_grants_only_mapped_permission(self):
        payload = {
            "wildcards": ["system:cashier"],
            "wildcard_permissions": {"system:cashier": ["read_pos", "operate_pos"]},
            "permissions": [],
        }
        self.assertTrue(has_context_permission(payload, "operate_pos"))
        self.assertFalse(has_context_permission(payload, "manage_pos_settings"))
