"""Safe social-auth account association hooks."""

from django.contrib.auth import get_user_model
from social_core.exceptions import AuthException, AuthForbidden


def associate_verified_google_by_email(
    backend,
    details,
    response,
    user=None,
    strategy=None,
    *args,
    **kwargs,
):
    """Link Google to an existing account only when Google verified the email."""
    if user or backend.name != "google-oauth2":
        return None

    email_verified = response.get("email_verified", response.get("verified_email", False))
    if email_verified not in (True, "true", "True", 1, "1"):
        raise AuthForbidden(backend)

    email = (details.get("email") or "").strip()
    if not email:
        return None

    users = list(
        get_user_model().objects.filter(email__iexact=email).only("pk")[:2]
    )
    if len(users) > 1:
        raise AuthException(
            backend,
            "The verified Google email is associated with multiple accounts.",
        )
    if users:
        return {"user": users[0], "is_new": False}

    request = getattr(strategy, "request", None)
    social_intent = ""
    if request is not None:
        social_intent = str(request.session.get("social_auth_intent", "login")).strip().lower()
    if social_intent != "signup":
        raise AuthException(
            backend,
            "No Intera IMS account exists for this Google email. Create an account first.",
        )
    return None


def preserve_existing_user_details(
    strategy,
    details,
    backend,
    user=None,
    is_new=False,
    *args,
    **kwargs,
):
    """Persist provider names only while creating a new social account.

    Names are protected globally so an existing account cannot be overwritten
    during login. That protection also applies to ``user_details`` though, so
    new SSO registrations need an explicit save after social-auth creates the
    user. Login deliberately does not fill missing names from the provider.
    """
    if user is None:
        return None

    if not is_new:
        return {"user": user}

    updates = {}
    for field in ("first_name", "last_name"):
        provider_value = str(details.get(field) or "").strip()
        if provider_value and getattr(user, field, "") != provider_value:
            setattr(user, field, provider_value)
            updates[field] = provider_value

    if updates:
        user.save(update_fields=list(updates))

    return {"user": user}
