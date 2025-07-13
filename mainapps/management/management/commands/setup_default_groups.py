from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from mainapps.permit.models import CombinedPermissions, CustomUserPermission
from ...models import CompanyProfile,StaffGroup
# from ...permissions.constants import CombinedPermissions

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
        
        default_groups = [
            {
                'name': 'Administrator',
                'description': 'Full access to all inventory and company management features',
                'permissions': [
                    # All inventory permissions
                    CombinedPermissions.CREATE_INVENTORY,
                    CombinedPermissions.READ_INVENTORY,
                    CombinedPermissions.UPDATE_INVENTORY,
                    CombinedPermissions.DELETE_INVENTORY,
                    CombinedPermissions.APPROVE_INVENTORY,
                    CombinedPermissions.VIEW_INVENTORY_REPORTS,
                    CombinedPermissions.MANAGE_INVENTORY_SETTINGS,
                    
                    # Purchase order permissions
                    CombinedPermissions.CREATE_PURCHASE_ORDER,
                    CombinedPermissions.READ_PURCHASE_ORDER,
                    CombinedPermissions.UPDATE_PURCHASE_ORDER,
                    CombinedPermissions.DELETE_PURCHASE_ORDER,
                    CombinedPermissions.APPROVE_PURCHASE_ORDER,
                    CombinedPermissions.ISSUE_PURCHASE_ORDER,
                    CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                    
                    # Stock management permissions
                    CombinedPermissions.CREATE_STOCK_ITEM,
                    CombinedPermissions.READ_STOCK_ITEM,
                    CombinedPermissions.UPDATE_STOCK_ITEM,
                    CombinedPermissions.DELETE_STOCK_ITEM,
                    CombinedPermissions.TRANSFER_STOCK_ITEM,
                    CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
                ]
            },
            {
                'name': 'Inventory Manager',
                'description': 'Manage inventory items and stock levels',
                'permissions': [
                    CombinedPermissions.CREATE_INVENTORY,
                    CombinedPermissions.READ_INVENTORY,
                    CombinedPermissions.UPDATE_INVENTORY,
                    CombinedPermissions.CREATE_STOCK_ITEM,
                    CombinedPermissions.READ_STOCK_ITEM,
                    CombinedPermissions.UPDATE_STOCK_ITEM,
                    CombinedPermissions.TRANSFER_STOCK_ITEM,
                    CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
                    CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
                ]
            },
            {
                'name': 'Purchase Manager',
                'description': 'Manage purchase orders and supplier relationships',
                'permissions': [
                    CombinedPermissions.CREATE_PURCHASE_ORDER,
                    CombinedPermissions.READ_PURCHASE_ORDER,
                    CombinedPermissions.UPDATE_PURCHASE_ORDER,
                    CombinedPermissions.APPROVE_PURCHASE_ORDER,
                    CombinedPermissions.ISSUE_PURCHASE_ORDER,
                    CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                    CombinedPermissions.CREATE_PURCHASE_ORDER_LINE_ITEM,
                    CombinedPermissions.READ_PURCHASE_ORDER_LINE_ITEM,
                    CombinedPermissions.UPDATE_PURCHASE_ORDER_LINE_ITEM,
                ]
            },
            {
                'name': 'Warehouse Staff',
                'description': 'Basic warehouse operations and stock handling',
                'permissions': [
                    CombinedPermissions.READ_INVENTORY,
                    CombinedPermissions.READ_STOCK_ITEM,
                    CombinedPermissions.UPDATE_STOCK_ITEM,
                    CombinedPermissions.TRANSFER_STOCK_ITEM,
                    CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                    CombinedPermissions.READ_STOCK_LOCATION,
                ]
            },
            {
                'name': 'Viewer',
                'description': 'Read-only access to inventory and reports',
                'permissions': [
                    CombinedPermissions.READ_INVENTORY,
                    CombinedPermissions.READ_STOCK_ITEM,
                    CombinedPermissions.READ_PURCHASE_ORDER,
                    CombinedPermissions.READ_STOCK_LOCATION,
                    CombinedPermissions.VIEW_INVENTORY_REPORTS,
                    CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
                ]
            }
        ]
        
        created_count = 0
        for group_data in default_groups:

            try:
                permissions=CustomUserPermission.objects.filter(codename__in= group_data['permissions'])
             
                group, created = StaffGroup.objects.get_or_create(
                    name=group_data['name'],
                    profile=profile,
                    defaults={
                        'description': group_data['description'],
                        # 'is_active': True
                    }
                )
                # for i,perm in enumerate(permissions):
                print('group: ',group)
                group.permissions.set(permissions)
                # print(i,' ',perm.codename)
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created group "{group.name}" for profile "{profile.name}"'
                        )
                    )
            except Exception as e:
                print(e)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {created_count} default groups for profile "{profile.name}"'
            )
        )
