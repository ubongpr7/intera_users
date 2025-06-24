from django.db.models.signals import post_save
from django.dispatch import receiver

from mainapps.permit.models import CombinedPermissions
from .models import CompanyProfile, StaffRole

@receiver(post_save, sender=CompanyProfile)
def create_default_roles(sender, instance, created, **kwargs):
    if created:
        create_roles_for_profile(instance)

def create_roles_for_profile(profile):
    """Create default roles for a company profile"""
    
    default_roles = [
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
    for role_data in default_roles:
        role, created = StaffRole.objects.get_or_create(
            name=role_data['name'],
            profile=profile,
            defaults={
                'description': role_data['description'],
            }
        )
        
        if created:
            # Convert enum permissions to actual permission objects
            PermissionModel = StaffRole.permissions.field.remote_field.model
            permission_codenames = [p.value for p in role_data['permissions']]
            permissions = PermissionModel.objects.filter(codename__in=permission_codenames)
            
            # Set permissions using .set()
            role.permissions.set(permissions)
            
    print(f'Created {created_count} default roles for profile "{profile.name}"')
