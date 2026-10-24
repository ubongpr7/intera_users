from django.core.management import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from mainapps.permit.models import (
    CombinedPermissions,
    CustomUserPermission,
    PermissionCategory,
    PlatformChoices,
)

class Command(BaseCommand):
    help = 'Populates the database with all permissions and their categories'
    
    def handle(self, *args, **options):
        self.stdout.write("Starting permission population...")
        
        # The database uniqueness boundary is (platform, codename). Category
        # or description changes are updates, not duplicate inserts.
        existing_perms = {
            permission.codename: permission
            for permission in CustomUserPermission.objects.filter(
                platform=PlatformChoices.INTERA_IMS
            )
        }
        
        # Create buffer for batch operations
        permissions_to_create = []
        permissions_to_update = []
        categories_to_create = {}
        
        with transaction.atomic():
            for codename, label in CombinedPermissions.choices:
                # Determine category name
                category_name = self._derive_category_name(codename)
                
                # Get or create category (batch optimized)
                if category_name not in categories_to_create:
                    category, created = PermissionCategory.objects.get_or_create(
                        name=category_name,
                        platform=PlatformChoices.INTERA_IMS,
                        defaults={'description': f"{category_name} related permissions"},
                    )
                    categories_to_create[category_name] = category
                
                category = categories_to_create[category_name]
                
                existing = existing_perms.get(codename)
                if existing is None:
                    permissions_to_create.append(CustomUserPermission(
                        codename=codename,
                        platform=PlatformChoices.INTERA_IMS,
                        category=category,
                        description=label  # Use label as description
                    ))
                else:
                    changed = False
                    if existing.category_id != category.id:
                        existing.category = category
                        changed = True
                    if existing.description != label:
                        existing.description = label
                        changed = True
                    if changed:
                        permissions_to_update.append(existing)
            
            # Bulk create new permissions
            batch_size = 100
            created_count = 0
            for i in range(0, len(permissions_to_create), batch_size):
                batch = permissions_to_create[i:i+batch_size]
                CustomUserPermission.objects.bulk_create(batch, batch_size)
                created_count += len(batch)
                self.stdout.write(f"Created {len(batch)} permissions...")
            if permissions_to_update:
                CustomUserPermission.objects.bulk_update(
                    permissions_to_update,
                    ["category", "description"],
                    batch_size=batch_size,
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed! Created {created_count} new permissions, "
                f"updated {len(permissions_to_update)} existing permissions. "
                f"Skipped {len(CombinedPermissions) - created_count - len(permissions_to_update)} unchanged entries."
            )
        )

    def _derive_category_name(self, codename):
        """
        Derives category name from permission codename using these rules:
        1. For full access permissions: "full_access_company" -> "Company"
        2. For other permissions: "create_company_address" -> "Company Address"
        3. Special handling for multi-word categories
        """
        # Handle full access permissions
        if codename.startswith('full_access_'):
            base = codename[12:]  # Remove 'full_access_'
        else:
            parts = codename.split('_')
            base = '_'.join(parts[1:]) if len(parts) > 1 else codename
        
        # Special cases for complex category names
        category_map = {
            'company_settings': 'Company',
            'agent_settings': 'Agent',
            'agent_activity': 'Agent',
            'with_agent': 'Agent',
            'inventory_reports': 'Inventory',
            'dashboard': 'Dashboard',
            'stock_item': 'Stock Item',
            'pos': 'POS',
            'pos_settings': 'POS',
            'pos_remittances': 'POS',
            'pos_reports': 'POS',
        }
        
        # Apply special mappings or general conversion
        return category_map.get(base, ' '.join(base.split('_')).title())
