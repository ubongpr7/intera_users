from django.test import SimpleTestCase

from mainapps.profile.models import LLMModel, LLMProviderChoices, ModelVersion, ProfileAgent


class ProfileAgentModelTests(SimpleTestCase):
    def test_effective_base_url_prefers_agent_override(self):
        llm = LLMModel(provider=LLMProviderChoices.gpt, base_url="https://api.openai.com")
        version = ModelVersion(llm=llm, model_name="gpt-5-mini")
        agent = ProfileAgent(version=version, base_url="https://custom-openai.example.com")

        self.assertEqual(agent.effective_base_url, "https://custom-openai.example.com")

    def test_effective_base_url_falls_back_to_provider_default(self):
        llm = LLMModel(provider=LLMProviderChoices.gpt, base_url="https://api.openai.com")
        version = ModelVersion(llm=llm, model_name="gpt-5-mini")
        agent = ProfileAgent(version=version, base_url="")

        self.assertEqual(agent.effective_base_url, "https://api.openai.com")
