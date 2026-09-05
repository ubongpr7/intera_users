from django.test import TestCase

from mainapps.accounts.authorization_context import decode_authorization_context, issue_authorization_context
from mainapps.accounts.models import User
from mainapps.accounts.serializers import CompanyContextSwitchSerializer
from mainapps.permit.models import PlatformChoices
from mainapps.profile.models import CompanyProfile


class HosperatorPlatformContextTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="hosperator-owner@example.com",
            password="password123",
        )
        self.profile = CompanyProfile.objects.create(
            owner=self.owner,
            name="Hosperator Owner Workspace",
        )

    def test_owner_context_is_compact_and_carries_hosperator_site_scope(self):
        context = decode_authorization_context(
            issue_authorization_context(
                self.owner,
                profile=self.profile,
                platform=PlatformChoices.HOSPERATOR,
            )
        )

        self.assertTrue(context["is_owner"])
        self.assertEqual(context["platform"], PlatformChoices.HOSPERATOR)
        self.assertNotIn("permissions", context)
        self.assertNotIn("wildcards", context)
        self.assertNotIn("wildcard_permissions", context)
        self.assertEqual(
            context["hosperator_care_site_scope"],
            {"version": 1, "care_site_ids": ["*"]},
        )

    def test_company_context_switch_accepts_requested_platform(self):
        serializer = CompanyContextSwitchSerializer(
            data={"profile_id": self.profile.id, "platform": PlatformChoices.HOSPERATOR}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["platform"], PlatformChoices.HOSPERATOR)
