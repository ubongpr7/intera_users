from djoser.social.token.jwt import TokenStrategy


class CustomSocialTokenStrategy(TokenStrategy):
    """Issue SimpleJWT tokens with our custom claims for social logins."""

    @classmethod
    def obtain(cls, user):
        refresh = cls._get_token(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
            "has_onboarded": user.has_onboarded,
            'plan_name': user.meta_data.get('plan', {}).get('slug'),
            'ai_simulations_left': user.meta_data.get('plan_features', {}).get('exam_attempts', {}).get('limit_value')
            
        }

    def _get_token(self, user):
        from .serializers import MyTokenObtainPairSerializer  

        return MyTokenObtainPairSerializer.get_token(user)
