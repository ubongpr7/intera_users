"""Safe social-auth account association hooks."""

from django.contrib.auth import get_user_model
from social_core.exceptions import AuthException, AuthForbidden
from social_core.pipeline.user import user_details


def associate_verified_google_by_email(
    backend,
    details,
    response,
    user=None,
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
    """Keep existing account names when a verified social identity is linked.

    New social accounts still receive provider details. Existing accounts keep
    the name already entered in Intera IMS instead of being overwritten by the
    provider's profile name.
    """
    if user is not None and not is_new:
        return {"user": user}
    return user_details(
        strategy,
        details,
        backend=backend,
        user=user,
        *args,
        **kwargs,
    )
