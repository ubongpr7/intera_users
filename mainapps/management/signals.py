from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.management import call_command
from mainapps.permit.models import CombinedPermissions
from .models import CompanyProfile, StaffRole
from threading import Thread

@receiver(post_save, sender=CompanyProfile)
def create_default_roles_and_groups(sender, instance, created, **kwargs):
    if created:
        role_thread = Thread(target=create_roles_for_profile, args=(instance,))
        role_thread.start()
        group_thread = Thread(target=create_groups_for_profile, args=(instance,))
        group_thread.start()


def create_roles_for_profile(profile):
    """Create default roles for a company profile"""
    try:
        call_command("setup_default_roles", '--profiel-id', f'{profile.id}')
    except Exception as e:
        print(f"Error processing video: {e}")

def create_groups_for_profile(profile):
    """Create default roles for a company profile"""
    try:
        call_command("setup_default_groups", f'--profiel-id',f'{profile.id}')
    except Exception as e:
        print(f"Error processing video: {e}")
