from django.core.management.base import BaseCommand

from mainapps.permit.models import PlatformChoices
from ...default_staff_presets import sync_system_staff_roles

class Command(BaseCommand):
    help = 'Create or update universal Intera system roles.'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--profile-id',
            type=str,
            help='Deprecated; system roles are universal.',
        )
        parser.add_argument(
            '--platform',
            choices=[choice.value for choice in PlatformChoices],
            default=PlatformChoices.INTERA_IMS,
            help='Product platform whose immutable system roles should be synchronized.',
        )
    
    def handle(self, *args, **options):
        result = sync_system_staff_roles(platform=options['platform'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {len(result["preset_names"])} universal system roles '
                f'({result["created_count"]} created, {result["updated_count"]} updated)'
            )
        )
