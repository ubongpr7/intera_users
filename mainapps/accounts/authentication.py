from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings


class AccountJWTAuthentication(JWTAuthentication):
    MFA_EXEMPT_PATH_PREFIXES = (
        "/auth/login/",
        "/auth/refresh/",
        "/auth/verify/",
        "/auth/logout/",
        "/auth/companies/",
        "/auth/switch-company/",
        "/accounts/mfa/setup/",
        "/accounts/mfa/verify/",
        "/accounts/mfa/toggle/",
        "/accounts/verify/",
    )

    def _is_mfa_exempt_path(self, request):
        path = getattr(request, "path", "") or ""
        return any(path.startswith(prefix) for prefix in self.MFA_EXEMPT_PATH_PREFIXES)

    def authenticate(self, request):
        try:
            header = self.get_header(request)
            if header is None:
                raw_token = request.COOKIES.get(settings.AUTH_COOKIE)
            else:
                raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None
            validated_token = self.get_validated_token(raw_token)
            if not self._is_mfa_exempt_path(request) and not bool(validated_token.get("mfa_verified", False)):
                raise AuthenticationFailed("MFA verification required.")
            return self.get_user(validated_token), validated_token
        except (InvalidToken, TokenError, AttributeError, TypeError, ValueError):
            return None
