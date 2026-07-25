from djoser.social.token.jwt import TokenStrategy


class CustomSocialTokenStrategy(TokenStrategy):
    """Issue SimpleJWT tokens with our custom claims for social logins."""

    @classmethod
    def obtain(cls, user):
        refresh = cls._get_token(user)
        profile = getattr(user, "profile", None)
        subscription_snapshot = getattr(profile, "subscription_snapshot", None) or {}
        subscription = subscription_snapshot.get("subscription") or {}
        features = subscription_snapshot.get("features") or {}
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
            "has_onboarded": user.has_onboarded,
            "plan_name": (subscription.get("plan") or {}).get("slug"),
            "ai_simulations_left": features.get("exam_attempts", {}).get("limit_value"),
            
        }

    def _get_token(self, user):
        from .serializers import MyTokenObtainPairSerializer  

        return MyTokenObtainPairSerializer.get_token(user)
