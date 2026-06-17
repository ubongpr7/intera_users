from django.core.management.base import BaseCommand

from ...default_staff_presets import sync_default_staff_roles
from ...models import CompanyProfile

class Command(BaseCommand):
    help = 'Create default roles and permissions for company profiles'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--profile-id',
            type=str,
            help='Company profile ID to create roles for',
        )
    
    def handle(self, *args, **options):
        profile_id = options.get('profile_id')
        
        if profile_id:
            try:
                profile = CompanyProfile.objects.get(id=profile_id)
                self.create_roles_for_profile(profile)
            except CompanyProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Company profile {profile_id} not found')
                )
        else:
            # Create roles for all profiles
            for profile in CompanyProfile.objects.all():
                self.create_roles_for_profile(profile)
    
    def create_roles_for_profile(self, profile):
        """Create default roles for a company profile"""
        result = sync_default_staff_roles(profile)
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {len(result["preset_names"])} default roles for profile "{profile.name}" '
                f'({result["created_count"]} created, {result["updated_count"]} updated)'
            )
        )
