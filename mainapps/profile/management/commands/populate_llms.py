from django.core.management.base import BaseCommand
from ...models import LLMModel, ModelVersion, LLMProviderChoices

class Command(BaseCommand):
    help = 'Populates LLMModel and ModelVersion tables with predefined LLM providers and models'

    def handle(self, *args, **options):
        # Define the provider and model version mapping
        llm_data = {
            LLMProviderChoices.gpt: [
                {
                    'model_name': 'gpt-5.4',
                    'versions': ['gpt-5.4', 'gpt-5.4-pro'],
                },
                {
                    'model_name': 'gpt-5',
                    'versions': ['gpt-5', 'gpt-5-pro', 'gpt-5-mini', 'gpt-5-nano'],
                },
                {
                    'model_name': 'gpt-codex',
                    'versions': ['gpt-5-codex', 'gpt-5.3-codex'],
                },
            ],
            LLMProviderChoices.gemini: [
                {
                    'model_name': 'gemini-3',
                    'versions': ['gemini-3-pro-preview', 'gemini-3-flash-preview'],
                },
                {
                    'model_name': 'gemini-2.5',
                    'versions': ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
                },
            ],
            LLMProviderChoices.grok: [
                {
                    'model_name': 'grok-4',
                    'versions': [
                        'grok-4',
                        'grok-4-fast-reasoning',
                        'grok-4-fast-non-reasoning',
                        'grok-4-1-fast-reasoning',
                        'grok-code-fast-1',
                    ],
                },
            ],
        }

        self.stdout.write(self.style.SUCCESS('Starting population of LLM models and versions...'))

        for provider, models in llm_data.items():
            # Check if the provider already exists in LLMModel
            llm_model, created = LLMModel.objects.get_or_create(
                provider=provider,
                defaults={'provider': provider}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created LLMModel: {provider}'))
            else:
                self.stdout.write(f'LLMModel {provider} already exists, skipping creation.')

            # Create ModelVersion instances for each model and version
            for model_data in models:
                for version_name in model_data['versions']:
                    model_version, created = ModelVersion.objects.get_or_create(
                        llm=llm_model,
                        model_name=version_name,
                        defaults={'model_name': version_name}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Created ModelVersion: {version_name} for {provider}'))
                    else:
                        self.stdout.write(f'ModelVersion {version_name} for {provider} already exists, skipping creation.')

        self.stdout.write(self.style.SUCCESS('Successfully populated LLM models and versions.'))
