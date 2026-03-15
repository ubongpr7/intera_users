from types import SimpleNamespace

from django.test import SimpleTestCase

from mainapps.accounts.serializers import MyTokenObtainPairSerializer


class Ka2aClaimTests(SimpleTestCase):
    def test_build_ka2a_claim_includes_effective_base_url(self):
        profile = SimpleNamespace(
            agent=SimpleNamespace(
                provider="chatgpt",
                model_name="gpt-5-mini",
                effective_base_url="https://api.openai.com",
                api_key="encrypted-openai-key",
                tavily_api_key="encrypted-tavily-key",
            )
        )

        claim = MyTokenObtainPairSerializer._build_ka2a_claim(profile)

        assert claim == {
            "v": 1,
            "llm": {
                "provider": "chatgpt",
                "model": "gpt-5-mini",
                "baseUrl": "https://api.openai.com",
                "apiKey": {"ciphertext": "encrypted-openai-key", "alg": "fernet"},
            },
            "tavily": {
                "apiKey": {"ciphertext": "encrypted-tavily-key", "alg": "fernet"},
            },
        }
