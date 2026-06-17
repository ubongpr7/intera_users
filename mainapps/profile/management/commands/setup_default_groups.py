from django.core.management.base import BaseCommand

from ...default_staff_presets import sync_default_staff_groups
from ...models import CompanyProfile

class Command(BaseCommand):
    help = 'Create default groups and permissions for company profiles'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--profile-id',
            type=str,
            help='Company profile ID to create groups for',
        )
    
    def handle(self, *args, **options):
        profile_id = options.get('profile_id')
        
        if profile_id:
            try:
                profile = CompanyProfile.objects.get(id=profile_id)
                self.create_groups_for_profile(profile)
            except CompanyProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Company profile {profile_id} not found')
                )
        else:
            # Create groups for all profiles
            for profile in CompanyProfile.objects.all():
                self.create_groups_for_profile(profile)
    
    def create_groups_for_profile(self, profile):
        """Create default groups for a company profile"""
        result = sync_default_staff_groups(profile)
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {len(result["preset_names"])} default groups for profile "{profile.name}" '
                f'({result["created_count"]} created, {result["updated_count"]} updated)'
            )
        )
