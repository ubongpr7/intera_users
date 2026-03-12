from django.core.management.base import BaseCommand
from ...models import LLMModel, ModelVersion, LLMProviderChoices

class Command(BaseCommand):
    help = 'Populates LLMModel and ModelVersion tables with predefined LLM providers and models'

    def handle(self, *args, **options):
        # Define the provider and model version mapping
        llm_data = {
            LLMProviderChoices.gpt: [
                {'model_name': 'gpt-4', 'versions': ['gpt-4-turbo', 'gpt-4o']},
                {'model_name': 'gpt-3.5', 'versions': ['gpt-3.5-turbo']},
            ],
            LLMProviderChoices.gemini: [
                {'model_name': 'gemini-1.5', 'versions': ['gemini-1.5-flash', 'gemini-1.5-pro']},
                {'model_name': 'gemini-1.0', 'versions': ['gemini-1.0-pro']},
            ],
            LLMProviderChoices.grok: [
                {'model_name': 'grok-3', 'versions': ['grok-3-base']},
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
                model_name = model_data['model_name']
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