from types import SimpleNamespace

from django.test import SimpleTestCase

from .serializers import MyTokenObtainPairSerializer


class SubscriptionAuthPayloadTests(SimpleTestCase):
    def test_profile_auth_payload_does_not_embed_subscription_snapshot(self):
        user = SimpleNamespace(id='user-1')
        profile = SimpleNamespace(
            id='profile-1',
            name='Workspace',
            company_code='WORKSPACE',
            logo=None,
            industry='retail',
            owner_id='user-1',
            currency='NGN',
        )

        payload = MyTokenObtainPairSerializer._profile_payload(profile, user)

        self.assertNotIn('subscription_snapshot', payload)
        self.assertNotIn('subscription', payload)
