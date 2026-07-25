import threading
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)
INTERA_BRAND = {
    "name": "Intera",
    "deep_blue": "#101727",
    "bright_blue": "#3c83f7",
    "light_green": "#98fcc2",
}


class EmailThread(threading.Thread):
    def __init__(self, email_message):
        self.email_message = email_message
        threading.Thread.__init__(self, daemon=True)

    def run(self):
        try:
            self.email_message.send(fail_silently=False)
            logger.info("Email sent successfully.")
        except Exception:
            logger.exception("Email delivery failed.")


def send_html_email(subject, message, to_email, html_file, context=None):
    frontend_site = getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
    template_context = {
        "subject": subject,
        "message": message,
        "brand": INTERA_BRAND,
        "brand_logo_url": f"{frontend_site}/assets/intera-logo.png" if frontend_site else "/assets/intera-logo.png",
        "brand_site_url": frontend_site or getattr(settings, "SITE_URL", "").strip().rstrip("/"),
    }
    if context:
        template_context.update(context)
    html_content = render_to_string(html_file, template_context)
    text_content = strip_tags(html_content)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER
    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    EmailThread(msg).start()
