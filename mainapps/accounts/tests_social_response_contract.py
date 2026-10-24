from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .serializers import MyTokenObtainPairSerializer, SocialJWTSerializer


class SocialResponseContractTests(SimpleTestCase):
    def test_created_session_survives_drf_representation(self):
        user = SimpleNamespace(
            id=42, username="tester", email="tester@example.com",
            first_name="Test", last_name="User", is_verified=True,
            is_staff=False, is_superuser=False, mfa_enabled=False,
            has_setup_mfa=False,
            get_picture=lambda: "/media/profile.jpg",
        )
        for profile in (None, SimpleNamespace(id=4, currency="NGN")):
            with self.subTest(has_workspace=profile is not None):
                access = SimpleNamespace(profile=profile, support_grant=None)
                context = {"id": "4", "name": "Test workspace"} if profile else None
                with (
                    patch.object(MyTokenObtainPairSerializer, "resolve_active_profile_access", return_value=access),
                    patch.object(MyTokenObtainPairSerializer, "issue_tokens_for_profile", return_value=("refresh", {"jti": "token-id"})) as issue,
                    patch.object(MyTokenObtainPairSerializer, "_profile_payload", return_value=context),
                    patch.object(MyTokenObtainPairSerializer, "list_accessible_profile_contexts", return_value=[access] if profile else []),
                    patch("mainapps.accounts.serializers.issue_authorization_context", return_value="signed-context"),
                ):
                    serializer = SocialJWTSerializer()
                    serializer.instance = serializer.create({"user": user})
                    response = serializer.data
                self.assertEqual(response["id"], 42)
                self.assertEqual(response["authorization_context"], "signed-context")
                self.assertEqual(response["profile"], "4" if profile else None)
                self.assertEqual(response["profile_context"], context)
                self.assertEqual(response["profiles"], [context] if profile else [])
                self.assertTrue(response["mfa_verified"])
                self.assertFalse(response["has_setup_mfa"])
                self.assertEqual(response["email"], user.email)
                self.assertEqual(response["picture"], "/media/profile.jpg")
                self.assertTrue(issue.call_args.kwargs["mfa_verified"])

    def test_workspace_less_claims_preserve_identity_and_sso_verification(self):
        user = SimpleNamespace(
            id=42, email="tester@example.com", is_staff=False, is_superuser=False,
            mfa_enabled=False, has_setup_mfa=False, referred_by_id=None,
        )
        password_claims = {}
        MyTokenObtainPairSerializer._apply_claims(password_claims, user, None)
        user._jwt_mfa_verified = True
        sso_claims = {}
        MyTokenObtainPairSerializer._apply_claims(sso_claims, user, None)
        self.assertEqual(sso_claims, {**password_claims, "mfa_verified": True})
        self.assertIsNone(sso_claims["profile_id"])
        self.assertIsNone(sso_claims["membership_role"])
        self.assertEqual(sso_claims["platform"], "intera_ims")
