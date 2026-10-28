from django.test import TestCase

from mainapps.accounts.api.serializers import RootUserCreateSerializer
from mainapps.accounts.models import AffiliatePartner, LegalConsent, ReferralPayout, User
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

        self.assertEqual(user.first_name, "Signup")
        self.assertEqual(user.last_name, "User")
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

        self.assertEqual(user.first_name, "Signup")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(LegalConsent.objects.filter(user=user).count(), 2)

    def test_djoser_signup_rejects_missing_first_name(self):
        data = self._data(
            email="missing-name@example.com",
            terms_accepted=True,
            privacy_accepted=True,
        )
        data.pop("first_name")

        serializer = UserCreateSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("first_name", serializer.errors)

    def test_new_users_receive_a_referral_code(self):
        user = User.objects.create_user(email="referrer@example.com", password=self.password)

        self.assertTrue(user.referral_code)
        self.assertEqual(user.referral_code, "REFERRER")

    def test_email_local_part_collision_falls_back_to_unique_code(self):
        User.objects.create_user(email="same@example.com", password=self.password)
        AffiliatePartner.objects.create(name="Existing partner", code="OTHER")

        second = User.objects.create_user(email="same@example.com.test", password=self.password)

        self.assertNotEqual(second.referral_code, "SAME")
        self.assertLessEqual(len(second.referral_code), 16)

    def test_email_derived_code_avoids_affiliate_partner_collision(self):
        AffiliatePartner.objects.create(name="Existing partner", code="BRAND")

        user = User.objects.create_user(email="brand@example.com", password=self.password)

        self.assertNotEqual(user.referral_code, "BRAND")

    def test_djoser_signup_links_a_referrer(self):
        referrer = User.objects.create_user(email="referrer@example.com", password=self.password)
        serializer = UserCreateSerializer(
            data=self._data(
                email="referred@example.com",
                referral_code=referrer.referral_code,
                terms_accepted=True,
                privacy_accepted=True,
            )
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        referred = serializer.save()

        self.assertEqual(referred.referred_by_id, referrer.id)

    def test_invalid_referral_code_is_rejected(self):
        serializer = UserCreateSerializer(
            data=self._data(
                email="invalid-referral@example.com",
                referral_code="NOT-A-REAL-CODE",
                terms_accepted=True,
                privacy_accepted=True,
            )
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("referral_code", serializer.errors)

    def test_payout_reference_is_idempotent(self):
        referrer = User.objects.create_user(email="referrer@example.com", password=self.password)
        referred = User.objects.create_user(
            email="referred@example.com",
            password=self.password,
            referred_by=referrer,
        )
        defaults = {
            "referrer_user": referrer,
            "referred_user": referred,
            "commission_rate": "0.05",
            "payment_amount": "100.00",
            "payout_amount": "5.00",
        }

        first, first_created = ReferralPayout.objects.get_or_create(
            payment_reference="payment-123",
            defaults=defaults,
        )
        second, second_created = ReferralPayout.objects.get_or_create(
            payment_reference="payment-123",
            defaults=defaults,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ReferralPayout.objects.filter(payment_reference="payment-123").count(), 1)
