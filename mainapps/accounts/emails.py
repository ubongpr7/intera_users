from django.conf import settings
from djoser.email import ActivationEmail, PasswordResetEmail

from subapps.utils.request_context import frontend_origin_from_request


def _static_asset_url(path):
    static_url = str(getattr(settings, "STATIC_URL", "") or "").strip()
    asset_path = str(path or "").lstrip("/")
    if not static_url or not asset_path:
        return ""
    if static_url.startswith(("http://", "https://")):
        return f"{static_url.rstrip('/')}/{asset_path}"
    site_url = str(getattr(settings, "SITE_URL", "") or "").strip().rstrip("/")
    if not site_url:
        return ""
    return f"{site_url}/{static_url.strip('/')}/{asset_path}"


def _brand_for_frontend(frontend_site):
    normalized = str(frontend_site or "").lower()
    if "hosperator" in normalized or "ospirator" in normalized:
        return {
            "name": "Hosperator",
            "support_email": "support@hosperator.com",
            "light_logo_path": "images/hosperator/hosperator-wordmark-light.png",
            "dark_logo_path": "images/hosperator/hosperator-wordmark-dark.png",
        }
    return {
        "name": "Intera IMS",
        "support_email": "support@interaims.com",
        "light_logo_path": "images/logos/INTERA-PRIMARY-LOGO-LIGHT-COLOR.png",
        "dark_logo_path": "images/logos/INTERA-EMAIL-LOGO-DARK.png",
    }


def build_intera_email_context(request=None):
    frontend_site = frontend_origin_from_request(request) if request is not None else ""
    frontend_site = frontend_site or getattr(settings, "FRONTEND_SITE_URL", "").strip().rstrip("/")
    site_url = getattr(settings, "SITE_URL", "").strip().rstrip("/")
    brand_site_url = frontend_site or site_url
    product_brand = _brand_for_frontend(brand_site_url)
    is_hosperator_brand = product_brand["name"] == "Hosperator"
    default_dark_logo_url = _static_asset_url(product_brand["dark_logo_path"])
    default_light_logo_url = _static_asset_url(product_brand["light_logo_path"])
    return {
        "brand": {
            "name": product_brand["name"],
            "deep_blue": "#101727",
            "bright_blue": "#3c83f7",
            "light_green": "#98fcc2",
            "surface": "#f5f9ff",
        },
        "brand_name": product_brand["name"],
        "brand_site_url": brand_site_url,
        "brand_logo_url": (
            default_dark_logo_url
            if is_hosperator_brand
            else getattr(settings, "EMAIL_BRAND_LOGO_URL", "")
            or getattr(settings, "EMAIL_BRAND_LOGO_DARK_URL", "")
            or default_dark_logo_url
        ),
        "brand_logo_light_url": (
            default_light_logo_url
            if is_hosperator_brand
            else getattr(settings, "EMAIL_BRAND_LOGO_LIGHT_URL", "") or default_light_logo_url
        ),
        "brand_logo_dark_url": (
            default_dark_logo_url
            if is_hosperator_brand
            else getattr(settings, "EMAIL_BRAND_LOGO_DARK_URL", "") or default_dark_logo_url
        ),
        "support_email": product_brand["support_email"]
        if is_hosperator_brand
        else getattr(settings, "EMAIL_SUPPORT_EMAIL", "") or product_brand["support_email"],
    }


class InteraActivationEmail(ActivationEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context.update(build_intera_email_context(self.request))
        if "://" in str(context.get("brand_site_url") or ""):
            protocol, domain = context["brand_site_url"].split("://", 1)
            context.update({"protocol": protocol, "domain": domain})
        return context


class InteraPasswordResetEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context.update(build_intera_email_context(self.request))
        if "://" in str(context.get("brand_site_url") or ""):
            protocol, domain = context["brand_site_url"].split("://", 1)
            context.update({"protocol": protocol, "domain": domain})
        return context
