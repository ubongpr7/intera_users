from django.core.exceptions import ImproperlyConfigured


PRODUCTION_ENVIRONMENTS = {"prod", "production"}


def env_bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_production_environment(value: str | None) -> bool:
    return (value or "").strip().lower() in PRODUCTION_ENVIRONMENTS


def validate_production_settings(
    *,
    debug: bool,
    local_server: bool,
    allowed_hosts: list[str],
    cors_allow_all: bool,
    cors_allowed_origins: list[str],
    csrf_trusted_origins: list[str],
    secure_ssl_redirect: bool,
    session_cookie_secure: bool,
    csrf_cookie_secure: bool,
    auth_cookie_secure: bool,
    hsts_seconds: int,
) -> None:
    errors: list[str] = []
    if debug:
        errors.append("DEBUG must be disabled")
    if local_server:
        errors.append("LOCAL_SERVER must be disabled")
    if not allowed_hosts or "*" in allowed_hosts:
        errors.append("ALLOWED_HOSTS must be explicit and must not contain '*'")
    if cors_allow_all:
        errors.append("CORS_ALLOW_ALL_ORIGINS must be disabled")
    if not cors_allowed_origins:
        errors.append("CORS_ALLOWED_ORIGINS must be explicitly configured")
    if any(not origin.startswith("https://") for origin in cors_allowed_origins):
        errors.append("CORS_ALLOWED_ORIGINS must use HTTPS origins")
    if any(not origin.startswith("https://") for origin in csrf_trusted_origins):
        errors.append("CSRF_TRUSTED_ORIGINS must use HTTPS origins")
    if not secure_ssl_redirect:
        errors.append("SECURE_SSL_REDIRECT must be enabled")
    if not session_cookie_secure or not csrf_cookie_secure or not auth_cookie_secure:
        errors.append("session, CSRF, and auth cookies must be secure")
    if hsts_seconds <= 0:
        errors.append("SECURE_HSTS_SECONDS must be greater than zero")
    if errors:
        raise ImproperlyConfigured("Unsafe production configuration: " + "; ".join(errors))
