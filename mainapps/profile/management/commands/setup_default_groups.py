from django.core.management.base import BaseCommand

from ...default_staff_presets import sync_system_staff_groups

class Command(BaseCommand):
    help = 'Create or update universal Intera system groups.'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--profile-id',
            type=str,
            help='Deprecated; system groups are universal.',
        )
    
    def handle(self, *args, **options):
        result = sync_system_staff_groups()
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {len(result["preset_names"])} universal system groups '
                f'({result["created_count"]} created, {result["updated_count"]} updated)'
            )
        )
