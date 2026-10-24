from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from social_core.exceptions import AuthException, AuthForbidden

from .social_pipeline import (
    associate_verified_google_by_email,
    preserve_existing_user_details,
)


class VerifiedGoogleAssociationTests(SimpleTestCase):
    def setUp(self):
        self.backend = SimpleNamespace(name="google-oauth2")

    def test_verified_google_email_links_existing_account_case_insensitively(self):
        existing = SimpleNamespace(pk=7)
        manager = SimpleNamespace(
            filter=lambda **kwargs: _QuerySet([existing], kwargs)
        )
        user_model = SimpleNamespace(objects=manager)

        with patch("mainapps.accounts.social_pipeline.get_user_model", return_value=user_model):
            result = associate_verified_google_by_email(
                self.backend,
                {"email": " User@Example.com "},
                {"email_verified": True},
            )

        self.assertEqual(result, {"user": existing, "is_new": False})

    def test_unverified_google_email_cannot_link_or_create_through_this_flow(self):
        with self.assertRaises(AuthForbidden):
            associate_verified_google_by_email(
                self.backend,
                {"email": "user@example.com"},
                {"email_verified": False},
            )

    def test_new_verified_google_email_continues_to_user_creation(self):
        manager = SimpleNamespace(filter=lambda **kwargs: _QuerySet([], kwargs))
        user_model = SimpleNamespace(objects=manager)
        strategy = SimpleNamespace(
            request=SimpleNamespace(session={"social_auth_intent": "signup"})
        )

        with patch("mainapps.accounts.social_pipeline.get_user_model", return_value=user_model):
            result = associate_verified_google_by_email(
                self.backend,
                {"email": "new@example.com"},
                {"email_verified": True},
                strategy=strategy,
            )

        self.assertIsNone(result)

    def test_new_verified_google_email_is_rejected_during_login(self):
        manager = SimpleNamespace(filter=lambda **kwargs: _QuerySet([], kwargs))
        user_model = SimpleNamespace(objects=manager)
        strategy = SimpleNamespace(
            request=SimpleNamespace(session={"social_auth_intent": "login"})
        )

        with patch("mainapps.accounts.social_pipeline.get_user_model", return_value=user_model):
            with self.assertRaisesRegex(AuthException, "Create an account first"):
                associate_verified_google_by_email(
                    self.backend,
                    {"email": "new@example.com"},
                    {"email_verified": True},
                    strategy=strategy,
                )

    def test_existing_account_details_are_not_overwritten_by_google(self):
        existing = SimpleNamespace(first_name="Intera", last_name="Name")
        result = preserve_existing_user_details(
            strategy=SimpleNamespace(),
            details={"first_name": "Google", "last_name": "Name"},
            backend=self.backend,
            user=existing,
            is_new=False,
        )

        self.assertEqual(result, {"user": existing})
        self.assertEqual(existing.first_name, "Intera")


class _QuerySet(list):
    def __init__(self, values, filters):
        super().__init__(values)
        self.filters = filters

    def only(self, *fields):
        return self
