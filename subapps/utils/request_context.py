from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import UntypedToken


def _get_token_payload(request):
    auth = getattr(request, "auth", None)
    if auth is not None:
        payload = getattr(auth, "payload", None)
        if payload is not None:
            return payload
        if isinstance(auth, dict):
            return auth
        if hasattr(auth, "get"):
            return auth

    auth_header = request.META.get("HTTP_AUTHORIZATION") or request.headers.get("Authorization")
    if not auth_header:
        return {}

    parts = auth_header.split()
    if len(parts) != 2:
        return {}

    try:
        return UntypedToken(parts[1]).payload
    except Exception:
        return {}


def get_request_claim(request, claim_name, default=None):
    return _get_token_payload(request).get(claim_name, default)


def get_request_profile_id(request, *, required=False, as_str=True):
    profile_id = get_request_claim(request, "profile_id")
    if profile_id in (None, ""):
        if required:
            raise AuthenticationFailed("Access token missing profile_id claim.")
        return None
    return str(profile_id) if as_str else profile_id


def get_request_user_id(request, *, required=False, as_str=True):
    user_id = getattr(getattr(request, "user", None), "id", None)
    if user_id in (None, ""):
        user_id = get_request_claim(request, "user_id")
    if user_id in (None, ""):
        user_id = get_request_claim(request, "id")
    if user_id in (None, ""):
        user_id = get_request_claim(request, "sub")
    if user_id in (None, ""):
        if required:
            raise AuthenticationFailed("Access token missing user identifier.")
        return None
    return str(user_id) if as_str else user_id


def get_request_permissions(request):
    permissions = get_request_claim(request, "permissions", [])
    if not permissions:
        return set()
    return set(permissions)


def get_request_company_code(request):
    return get_request_claim(request, "company_code")


def get_request_support_access_grant_id(request):
    return get_request_claim(request, "support_access_grant_id")


def get_request_email(request):
    return get_request_claim(request, "email")


def get_request_full_name(request):
    return get_request_claim(request, "full_name") or get_request_claim(request, "name")


def get_request_auth_headers(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION") or request.headers.get("Authorization")
    if not auth_header:
        return {}
    return {"Authorization": auth_header}


def normalize_frontend_origin(value):
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))


def allowed_frontend_origins():
    configured = getattr(settings, "FRONTEND_ACTION_ALLOWED_ORIGINS", None)
    if configured is None:
        configured = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
    origins = [
        *list(configured or []),
        getattr(settings, "FRONTEND_SITE_URL", ""),
        getattr(settings, "SITE_URL", ""),
    ]
    return {origin for origin in (normalize_frontend_origin(item) for item in origins) if origin}


def frontend_origin_from_request(request, *, default=None):
    candidates = [
        request.headers.get("X-Intera-Frontend-Origin"),
        request.headers.get("X-Frontend-Origin"),
        request.headers.get("Origin"),
        request.headers.get("Referer"),
        default,
        getattr(settings, "FRONTEND_SITE_URL", ""),
        getattr(settings, "SITE_URL", ""),
    ]
    allowed = allowed_frontend_origins()
    for candidate in candidates:
        origin = normalize_frontend_origin(candidate)
        if origin and (not allowed or origin in allowed):
            return origin
    return ""


def build_frontend_url(request, path, *, default=None):
    origin = frontend_origin_from_request(request, default=default)
    if not origin:
        return ""
    return f"{origin}/{str(path or '').lstrip('/')}"


def get_identity_cache_key(request, default="default"):
    profile_id = get_request_profile_id(request)
    if profile_id in (None, ""):
        return default
    return str(profile_id)


def coerce_identity_id(value):
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _lookup_path_exists(model, lookup_path):
    if model is None or not lookup_path:
        return False

    current_model = model
    parts = lookup_path.split("__")
    for index, part in enumerate(parts):
        try:
            field = current_model._meta.get_field(part)
        except FieldDoesNotExist:
            return False

        if index == len(parts) - 1:
            return True

        current_model = getattr(getattr(field, "remote_field", None), "model", None)
        if current_model is None:
            return False

    return True


def build_identity_lookup(*, canonical_field, legacy_field=None, value=None, model=None):
    lookup = Q()
    normalized_value = coerce_identity_id(value)
    legacy_value = None if value in (None, "") else str(value).strip()

    if normalized_value is not None and _lookup_path_exists(model, canonical_field):
        lookup |= Q(**{canonical_field: normalized_value})
        legacy_value = str(normalized_value)

    if legacy_field and legacy_value not in (None, "") and _lookup_path_exists(model, legacy_field):
        lookup |= Q(**{legacy_field: legacy_value})

    return lookup


def scope_queryset_by_identity(queryset, *, canonical_field, legacy_field=None, value=None):
    lookup = build_identity_lookup(
        canonical_field=canonical_field,
        legacy_field=legacy_field,
        value=value,
        model=queryset.model,
    )
    if not lookup.children:
        return queryset
    return queryset.filter(lookup)
