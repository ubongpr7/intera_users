from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from mainapps.accounts.emails import InteraActivationEmail, InteraPasswordResetEmail
from mainapps.accounts.models import User


@override_settings(
    DEFAULT_FROM_EMAIL="Intera Accounts <noreply@example.test>",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_SITE_URL="https://dev.interaims.com",
    SITE_URL="https://dev.interaims.com",
    FRONTEND_ACTION_ALLOWED_ORIGINS=[
        "https://dev.interaims.com",
        "https://dev.hosperator.com",
    ],
    EMAIL_BRAND_LOGO_URL="https://assets.example/intera-email-logo.png",
)
class ActivationEmailRenderingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="activation@example.com",
            password="SecurePassword123!",
            first_name="Activation",
        )
        mail.outbox = []

    def test_activation_email_renders_subject_body_and_hosperator_origin_link(self):
        request = self.factory.post(
            "/djoser/users/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.hosperator.com",
        )

        InteraActivationEmail(request=request, context={"user": self.user}).send([self.user.email])

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Activate your Hosperator account")
        self.assertIn("Welcome to Hosperator.", message.body)
        self.assertIn("https://dev.hosperator.com/activate/", message.body)
        self.assertEqual(len(message.alternatives), 1)
        self.assertIn("Welcome to Hosperator", message.alternatives[0][0])
        self.assertIn("/images/hosperator/hosperator-wordmark-dark.png", message.alternatives[0][0])

    def test_activation_email_keeps_intera_brand_for_intera_origin(self):
        request = self.factory.post(
            "/djoser/users/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.interaims.com",
        )

        InteraActivationEmail(request=request, context={"user": self.user}).send([self.user.email])

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Activate your Intera IMS account")
        self.assertIn("Welcome to Intera IMS.", message.body)
        self.assertIn("https://dev.interaims.com/activate/", message.body)
        self.assertNotIn("Hosperator", message.body)
        self.assertIn("https://assets.example/intera-email-logo.png", message.alternatives[0][0])

    def test_password_reset_email_renders_non_empty_subject_and_body(self):
        request = self.factory.post(
            "/djoser/users/reset_password/",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.interaims.com",
        )

        InteraPasswordResetEmail(request=request, context={"user": self.user}).send([self.user.email])

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reset your Intera IMS password")
        self.assertIn("We received a request to reset your Intera IMS password.", message.body)
        self.assertIn("https://dev.interaims.com/accounts/password_reset/", message.body)
        self.assertEqual(len(message.alternatives), 1)

    def test_resend_activation_endpoint_sends_rendered_email(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            "/djoser/users/resend_activation/",
            {"email": self.user.email},
            format="json",
            HTTP_X_INTERA_FRONTEND_ORIGIN="https://dev.hosperator.com",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Activate your Hosperator account")
        self.assertIn("https://dev.hosperator.com/activate/", mail.outbox[0].body)
