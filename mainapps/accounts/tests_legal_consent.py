from django.test import TestCase

from mainapps.accounts.api.serializers import RootUserCreateSerializer
from mainapps.accounts.models import LegalConsent
from mainapps.accounts.serializers import UserCreateSerializer


class SignupLegalConsentTests(TestCase):
    password = "SecurePassword123!"

    def _data(self, email="signup@example.com", **consents):
        return {
            "first_name": "Signup",
            "last_name": "User",
            "email": email,
            "password": self.password,
            "re_password": self.password,
            **consents,
        }

    def test_root_signup_requires_both_policies(self):
        serializer = RootUserCreateSerializer(data=self._data())

        self.assertFalse(serializer.is_valid())
        self.assertIn("terms_accepted", serializer.errors)
        self.assertIn("privacy_accepted", serializer.errors)

    def test_root_signup_records_both_policy_acceptances(self):
        serializer = RootUserCreateSerializer(
            data=self._data(terms_accepted=True, privacy_accepted=True)
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(
            LegalConsent.objects.filter(user=user).values_list("consent_type", flat=True).count(),
            2,
        )

    def test_djoser_signup_requires_both_policies(self):
        serializer = UserCreateSerializer(
            data=self._data(email="djoser@example.com")
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("terms_accepted", serializer.errors)
        self.assertIn("privacy_accepted", serializer.errors)

    def test_djoser_signup_records_both_policy_acceptances(self):
        serializer = UserCreateSerializer(
            data=self._data(
                email="djoser-accepted@example.com",
                terms_accepted=True,
                privacy_accepted=True,
            )
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(LegalConsent.objects.filter(user=user).count(), 2)
