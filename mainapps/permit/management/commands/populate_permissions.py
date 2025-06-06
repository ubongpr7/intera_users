from django.core.management import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from mainapps.permit.models import CombinedPermissions, CustomUserPermission, PermissionCategory

class Command(BaseCommand):
    help = 'Populates the database with all permissions and their categories'
    
    def handle(self, *args, **options):
        self.stdout.write("Starting permission population...")
        
        # Get all existing permissions once for comparison
        existing_perms = set(CustomUserPermission.objects.values_list('codename', 'category__name'))
        
        # Create buffer for batch operations
        permissions_to_create = []
        categories_to_create = {}
        
        with transaction.atomic():
            for codename, label in CombinedPermissions.choices:
                # Determine category name
                category_name = self._derive_category_name(codename)
                
                # Get or create category (batch optimized)
                if category_name not in categories_to_create:
                    category, created = PermissionCategory.objects.get_or_create(
                        name=category_name,
                        defaults={'description': f"{category_name} related permissions"}
                    )
                    categories_to_create[category_name] = category
                
                category = categories_to_create[category_name]
                
                # Skip existing permissions
                if (codename, category.name) not in existing_perms:
                    permissions_to_create.append(CustomUserPermission(
                        codename=codename,
                        category=category,
                        description=label  # Use label as description
                    ))
            
            # Bulk create new permissions
            batch_size = 100
            created_count = 0
            for i in range(0, len(permissions_to_create), batch_size):
                batch = permissions_to_create[i:i+batch_size]
                CustomUserPermission.objects.bulk_create(batch, batch_size)
                created_count += len(batch)
                self.stdout.write(f"Created {len(batch)} permissions...")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed! Created {created_count} new permissions. "
                f"Skipped {len(CombinedPermissions) - created_count} existing entries."
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
            'inventory_reports': 'Inventory',
            'dashboard': 'Dashboard',
            'stock_item': 'Stock Item'
        }
        
        # Apply special mappings or general conversion
        return category_map.get(base, ' '.join(base.split('_')).title())