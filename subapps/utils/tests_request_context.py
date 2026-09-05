from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from subapps.kafka.producers.platform_events import publish_workspace_notification
from subapps.kafka.producers.support_access import build_actor
from subapps.utils.request_context import build_frontend_url, frontend_origin_from_request


class FrontendOriginRequestContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(
        FRONTEND_SITE_URL="https://dev.interaims.com",
        SITE_URL="https://dev.interaims.com",
        FRONTEND_ACTION_ALLOWED_ORIGINS=[
            "https://dev.interaims.com",
            "https://dev.hosperator.com",
        ],
    )
    def test_uses_allowed_frontend_origin_header(self):
        request = self.factory.post(
            "/djoser/users/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.hosperator.com",
        )

        assert frontend_origin_from_request(request) == "https://dev.hosperator.com"
        assert (
            build_frontend_url(request, "/activate/uid/token")
            == "https://dev.hosperator.com/activate/uid/token"
        )

    @override_settings(
        FRONTEND_SITE_URL="https://dev.interaims.com",
        SITE_URL="https://dev.interaims.com",
        FRONTEND_ACTION_ALLOWED_ORIGINS=["https://dev.interaims.com"],
    )
    def test_rejects_unapproved_frontend_origin_header(self):
        request = self.factory.post(
            "/djoser/users/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://attacker.example",
        )

        assert frontend_origin_from_request(request) == "https://dev.interaims.com"
        assert (
            build_frontend_url(request, "/accounts/register?ref=abc")
            == "https://dev.interaims.com/accounts/register?ref=abc"
        )

    @override_settings(
        FRONTEND_SITE_URL="https://dev.interaims.com",
        SITE_URL="https://dev.interaims.com",
        FRONTEND_ACTION_ALLOWED_ORIGINS=[
            "https://dev.interaims.com",
            "https://dev.hosperator.com",
        ],
    )
    def test_notification_actor_propagates_frontend_origin(self):
        request = self.factory.post(
            "/profile/memberships/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.hosperator.com",
        )
        actor = build_actor(request=request)

        assert actor["frontend_origin"] == "https://dev.hosperator.com"

        with patch("subapps.kafka.producers.platform_events.publish_event") as publish_event_mock:
            publish_workspace_notification(
                event_name="notification.identity.user.permissions.updated",
                workspace_id="workspace-1",
                category="security",
                title="Your workspace access changed",
                message="Your permissions were updated.",
                metadata={"user_id": "user-1"},
                action_url="/notifications",
                actor=actor,
                user_ids=["user-1"],
            )

        payload = publish_event_mock.call_args.args[2]
        assert payload["frontend_origin"] == "https://dev.hosperator.com"
        assert payload["action_url"] == "/notifications"
