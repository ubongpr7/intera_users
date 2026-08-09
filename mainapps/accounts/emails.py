from django.conf import settings
from djoser.email import ActivationEmail, PasswordResetEmail


def build_intera_email_context():
    frontend_site = getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
    site_url = getattr(settings, "SITE_URL", "").strip().rstrip("/")
    brand_site_url = frontend_site or site_url
    logo_base_url = brand_site_url
    white_logo = "/assets/img/logos/verticals/no-bg/INTERA-PRIMARY-LOGO-VERTICAL-WHITE-4.png"
    black_logo = "/assets/img/logos/verticals/no-bg/INTERA-PRIMARY-LOGO-VERTICAL-BLACK-3.png"
    return {
        "brand": {
            "name": "Intera IMS",
            "deep_blue": "#101727",
            "bright_blue": "#3c83f7",
            "light_green": "#98fcc2",
            "surface": "#f5f9ff",
        },
        "brand_name": "Intera IMS",
        "brand_site_url": brand_site_url,
        "brand_logo_url": getattr(settings, "EMAIL_BRAND_LOGO_URL", "")
        or getattr(settings, "EMAIL_BRAND_LOGO_DARK_URL", "")
        or (f"{logo_base_url}{white_logo}" if logo_base_url else ""),
        "brand_logo_light_url": getattr(settings, "EMAIL_BRAND_LOGO_LIGHT_URL", "")
        or (f"{logo_base_url}{black_logo}" if logo_base_url else ""),
        "brand_logo_dark_url": getattr(settings, "EMAIL_BRAND_LOGO_DARK_URL", "")
        or (f"{logo_base_url}{white_logo}" if logo_base_url else ""),
        "support_email": getattr(settings, "EMAIL_SUPPORT_EMAIL", "") or "support@interaims.com",
    }


class InteraActivationEmail(ActivationEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context.update(build_intera_email_context())
        return context


class InteraPasswordResetEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context.update(build_intera_email_context())
        return context
