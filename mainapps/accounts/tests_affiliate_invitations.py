from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import AffiliatePartner, AffiliatePartnerInvitation, User


@override_settings(FRONTEND_SITE_URL="https://www.interaims.com")
class AffiliatePartnerInvitationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser("admin@example.com", password="StrongPassword123!")
        self.client.force_authenticate(self.admin)

    @patch("mainapps.accounts.views.send_html_email")
    def test_creation_provisions_account_and_acceptance_activates_it(self, send_email):
        response = self.client.post("/accounts/affiliate-partners/", {
            "name": "Partner One",
            "email": "partner@example.com",
            "code": "PARTNERONE",
            "commission_rate": "0.05",
            "is_active": True,
        }, format="json")

        self.assertEqual(response.status_code, 201)
        partner = AffiliatePartner.objects.get(code="PARTNERONE")
        invited_user = User.objects.get(email="partner@example.com")
        invitation = AffiliatePartnerInvitation.objects.get(partner=partner)
        self.assertEqual(partner.account_user_id, invited_user.id)
        self.assertTrue(invited_user.is_affiliate_marketer)
        self.assertEqual(invited_user.referral_code, "PARTNERONE")
        self.assertEqual(str(invited_user.referral_commission_rate), "0.05000")
        self.assertEqual(send_email.call_args.kwargs["context"]["commission_rate_display"], "5%")
        self.assertFalse(invited_user.has_usable_password())
        invite_url = send_email.call_args.kwargs["context"]["invite_url"]
        token = invite_url.rsplit("/", 1)[-1]

        self.client.force_authenticate(None)
        accepted = self.client.post("/accounts/affiliate-partner-invitations/accept/", {
            "token": token,
            "first_name": "Partner",
            "last_name": "One",
            "password": "StrongPassword123!",
        }, format="json")

        self.assertEqual(accepted.status_code, 200)
        invited_user.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(invited_user.has_usable_password())
        self.assertTrue(invited_user.is_verified)
        self.assertTrue(invited_user.is_affiliate_marketer)
        self.assertIsNone(invited_user.referred_by_affiliate_partner_id)
        self.assertEqual(invitation.status, AffiliatePartnerInvitation.Status.ACCEPTED)

        self.client.force_authenticate(invited_user)
        referrals = self.client.get("/accounts/users/referrals/")
        self.assertEqual(referrals.status_code, 200)
        self.assertEqual(referrals.data["referred_count"], 0)
        self.assertEqual(referrals.data["referred_users"], [])

    @patch("mainapps.accounts.views.send_html_email")
    def test_partner_edit_persists_code_and_commission(self, send_email):
        created = self.client.post("/accounts/affiliate-partners/", {
            "name": "Partner Two",
            "email": "partner-two@example.com",
            "code": "PARTNERTWO",
            "commission_rate": "0.05",
            "is_active": True,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        partner = AffiliatePartner.objects.get(code="PARTNERTWO")

        response = self.client.patch(
            f"/accounts/affiliate-partners/{partner.pk}/",
            {"code": "PARTNERUPDATED", "commission_rate": "0.10"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        partner.refresh_from_db()
        self.assertEqual(partner.code, "PARTNERUPDATED")
        self.assertEqual(str(partner.commission_rate), "0.10000")
        partner.account_user.refresh_from_db()
        self.assertTrue(partner.account_user.is_affiliate_marketer)
        self.assertEqual(partner.account_user.referral_code, "PARTNERUPDATED")
        self.assertEqual(str(partner.account_user.referral_commission_rate), "0.10000")

    @patch("mainapps.accounts.views.send_html_email")
    def test_referral_dashboard_uses_partner_identity_and_counts_only_partner_referrals(self, send_email):
        created = self.client.post("/accounts/affiliate-partners/", {
            "name": "Affiliate One",
            "email": "affiliate-one@example.com",
            "code": "AFFILIATEONE",
            "commission_rate": "0.20",
            "is_active": True,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        partner = AffiliatePartner.objects.get(code="AFFILIATEONE")
        affiliate_user = partner.account_user

        self.client.force_authenticate(affiliate_user)
        response = self.client.get("/accounts/users/referrals/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["referral_code"], "AFFILIATEONE")
        self.assertEqual(response.data["commission_rate"], "0.20000")
        self.assertEqual(response.data["referred_count"], 0)
        self.assertEqual(response.data["referred_users"], [])
