from django.db import models
from django.utils.translation import gettext_lazy as _

class PermissionCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=30, blank=True)
    
    class Meta:
        verbose_name_plural = "Permission Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class CombinedPermissions(models.TextChoices):
    # Company Permissions
    CREATE_COMPANY = 'create_company', _('Can create company')
    READ_COMPANY = 'read_company', _('Can read company')
    UPDATE_COMPANY = 'update_company', _('Can update company')
    DELETE_COMPANY = 'delete_company', _('Can delete company')
    APPROVE_COMPANY = 'approve_company', _('Can approve company')
    REJECT_COMPANY = 'reject_company', _('Can reject company')
    MANAGE_COMPANY_SETTINGS = 'manage_company_settings', _('Can manage company settings')

    # Contact Permissions
    CREATE_CONTACT = 'create_contact', _('Can create contact')
    READ_CONTACT = 'read_contact', _('Can read contact')
    UPDATE_CONTACT = 'update_contact', _('Can update contact')
    DELETE_CONTACT = 'delete_contact', _('Can delete contact')
    MANAGE_CONTACT_SETTINGS = 'manage_contact_settings', _('Can manage contact settings')

    # Company Address Permissions
    CREATE_COMPANY_ADDRESS = 'create_company_address', _('Can create company address')
    READ_COMPANY_ADDRESS = 'read_company_address', _('Can read company address')
    UPDATE_COMPANY_ADDRESS = 'update_company_address', _('Can update company address')
    DELETE_COMPANY_ADDRESS = 'delete_company_address', _('Can delete company address')
    MANAGE_COMPANY_ADDRESS_SETTINGS = 'manage_company_address_settings', _('Can manage company address settings')

    # Inventory Permissions
    CREATE_INVENTORY = 'create_inventory', _('Can create inventory')
    READ_INVENTORY = 'read_inventory', _('Can read inventory')
    UPDATE_INVENTORY = 'update_inventory', _('Can update inventory')
    DELETE_INVENTORY = 'delete_inventory', _('Can delete inventory')
    APPROVE_INVENTORY = 'approve_inventory', _('Can approve inventory')
    REJECT_INVENTORY = 'reject_inventory', _('Can reject inventory')
    ARCHIVE_INVENTORY = 'archive_inventory', _('Can archive inventory')
    RESTORE_INVENTORY = 'restore_inventory', _('Can restore archived inventory')
    MANAGE_INVENTORY_SETTINGS = 'manage_inventory_settings', _('Can manage inventory settings')
    VIEW_INVENTORY_REPORTS = 'view_inventory_reports', _('Can view inventory reports')
    VIEW_DASHBOARD_REPORTS = 'can_view_dashboard', _('Can view Dashboard reports')

    CREATE_INVENTORY_CATEGORY = 'create_inventory_category', _('Can create inventory')
    READ_INVENTORY_CATEGORY = 'read_inventory_category', _('Can read inventory')
    UPDATE_INVENTORY_CATEGORY = 'update_inventory_category', _('Can update inventory')
    DELETE_INVENTORY_CATEGORY = 'delete_inventory_category', _('Can delete inventory')
    APPROVE_INVENTORY_CATEGORY = 'approve_inventory_category', _('Can approve inventory')
    # Purchase Order Permissions
    CREATE_PURCHASE_ORDER = 'create_purchase_order', _('Can create purchase order')
    READ_PURCHASE_ORDER = 'read_purchase_order', _('Can read purchase order')
    UPDATE_PURCHASE_ORDER = 'update_purchase_order', _('Can update purchase order')
    DELETE_PURCHASE_ORDER = 'delete_purchase_order', _('Can delete purchase order')
    APPROVE_PURCHASE_ORDER = 'approve_purchase_order', _('Can approve purchase order')
    REJECT_PURCHASE_ORDER = 'reject_purchase_order', _('Can reject purchase order')
    ISSUE_PURCHASE_ORDER = 'issue_purchase_order', _('Can issue purchase order')
    RECEIVE_PURCHASE_ORDER = 'receive_purchase_order', _('Can receive purchase order')
    CANCEL_PURCHASE_ORDER = 'cancel_purchase_order', _('Can cancel purchase order')
    VIEW_PURCHASE_ORDER_HISTORY = 'view_purchase_order_history', _('Can view purchase order history')
    EDIT_PURCHASE_ORDER_DETAILS = 'edit_purchase_order_details', _('Can edit purchase order details')
    ASSIGN_PURCHASE_ORDER_TO_SUPPLIER = 'assign_purchase_order_to_supplier', _('Can assign purchase order to supplier')
    CHANGE_SUPPLIER_FOR_PURCHASE_ORDER = 'change_supplier_for_purchase_order', _('Can change supplier for purchase order')
    ADD_NOTES_TO_PURCHASE_ORDER = 'add_notes_to_purchase_order', _('Can add notes to purchase order')
    ATTACH_DOCUMENTS_TO_PURCHASE_ORDER = 'attach_documents_to_purchase_order', _('Can attach documents to purchase order')
    SET_PURCHASE_ORDER_PRIORITY = 'set_purchase_order_priority', _('Can set purchase order priority')
    SPLIT_PURCHASE_ORDER = 'split_purchase_order', _('Can split purchase order')
    MERGE_PURCHASE_ORDERS = 'merge_purchase_orders', _('Can merge purchase orders')
    CREATE_PURCHASE_ORDER_TEMPLATE = 'create_purchase_order_template', _('Can create purchase order template')
    USE_PURCHASE_ORDER_TEMPLATE = 'use_purchase_order_template', _('Can use purchase order template')
    EXPORT_PURCHASE_ORDERS = 'export_purchase_orders', _('Can export purchase orders')
    IMPORT_PURCHASE_ORDERS = 'import_purchase_orders', _('Can import purchase orders')
    GENERATE_PURCHASE_ORDER_REPORTS = 'generate_purchase_order_reports', _('Can generate purchase order reports')
    NOTIFY_USERS_ABOUT_PURCHASE_ORDER_STATUS = 'notify_users_about_purchase_order_status', _('Can notify users about purchase order status')
    MANAGE_PURCHASE_ORDER_SETTINGS = 'manage_purchase_order_settings', _('Can manage purchase order settings')

    CREATE_PURCHASE_ORDER_LINE_ITEM = 'create_purchase_order_line_item', _('Can create purchase order line item')
    READ_PURCHASE_ORDER_LINE_ITEM = 'read_purchase_order_line_item', _('Can read purchase order line item')
    UPDATE_PURCHASE_ORDER_LINE_ITEM = 'update_purchase_order_line_item', _('Can update purchase order line item')
    DELETE_PURCHASE_ORDER_LINE_ITEM = 'delete_purchase_order_line_item', _('Can delete purchase order line item')
    # Sales Order Permissions

    # return order
    CREATE_RETURN_ORDER = 'create_return_order', _('Can create return order')
    READ_RETURN_ORDER = 'read_return_order', _('Can read return order')
    UPDATE_RETURN_ORDER = 'update_return_order', _('Can update return order')
    DELETE_RETURN_ORDER = 'delete_return_order', _('Can delete return order')
    APPROVE_RETURN_ORDER = 'approve_return_order', _('Can approve return order')
    REJECT_RETURN_ORDER = 'reject_return_order', _('Can reject return order')
    PROCESS_RETURN_ORDER = 'process_return_order', _('Can process return order')
    COMPLETE_RETURN_ORDER = 'complete_return_order', _('Can complete return order')
    CANCEL_RETURN_ORDER = 'cancel_return_order', _('Can cancel return order')
    VIEW_RETURN_ORDER_HISTORY = 'view_return_order_history', _('Can view return order history')
    EDIT_RETURN_ORDER_DETAILS = 'edit_return_order_details', _('Can edit return order details')
    ASSIGN_RETURN_ORDER_TO_WAREHOUSE = 'assign_return_order_to_warehouse', _('Can assign return order to warehouse')
    CHANGE_PURCHASE_ORDER_FOR_RETURN = 'change_purchase_order_for_return', _('Can change purchase order for return')
    ADD_NOTES_TO_RETURN_ORDER = 'add_notes_to_return_order', _('Can add notes to return order')
    ATTACH_DOCUMENTS_TO_RETURN_ORDER = 'attach_documents_to_return_order', _('Can attach documents to return order')
    SET_RETURN_ORDER_PRIORITY = 'set_return_order_priority', _('Can set return order priority')
    SPLIT_RETURN_ORDER = 'split_return_order', _('Can split return order')
    MERGE_RETURN_ORDERS = 'merge_return_orders', _('Can merge return orders')
    CREATE_RETURN_ORDER_TEMPLATE = 'create_return_order_template', _('Can create return order template')
    USE_RETURN_ORDER_TEMPLATE = 'use_return_order_template', _('Can use return order template')
    EXPORT_RETURN_ORDERS = 'export_return_orders', _('Can export return orders')
    IMPORT_RETURN_ORDERS = 'import_return_orders', _('Can import return orders')
    GENERATE_RETURN_ORDER_REPORTS = 'generate_return_order_reports', _('Can generate return order reports')
    NOTIFY_SUPPLIERS_ABOUT_RETURN = 'notify_suppliers_about_return', _('Can notify suppliers about return status')
    MANAGE_RETURN_ORDER_SETTINGS = 'manage_return_order_settings', _('Can manage return order settings')
    AUTHORIZE_RETURN_REFUND = 'authorize_return_refund', _('Can authorize return refunds')
    VERIFY_RETURN_CONDITION = 'verify_return_condition', _('Can verify returned item condition')
    MANAGE_RETURN_INVENTORY = 'manage_return_inventory', _('Can manage returned inventory')
    EDIT_RETURN_REASON = 'edit_return_reason', _('Can edit return reasons')
    OVERRIDE_RETURN_POLICY = 'override_return_policy', _('Can override return policy exceptions')
    TRACK_RETURN_SHIPMENT = 'track_return_shipment', _('Can track return shipments')
    ACCEPT_RETURN_DISCREPANCIES = 'accept_return_discrepancies', _('Can accept return quantity discrepancies')
    MANAGE_RETURN_CREDITS = 'manage_return_credits', _('Can manage return credits')

    CREATE_SALES_ORDER = 'create_sales_order', _('Can create sales order')
    READ_SALES_ORDER = 'read_sales_order', _('Can read sales order')
    UPDATE_SALES_ORDER = 'update_sales_order', _('Can update sales order')
    DELETE_SALES_ORDER = 'delete_sales_order', _('Can delete sales order')
    APPROVE_SALES_ORDER = 'approve_sales_order', _('Can approve sales order')
    REJECT_SALES_ORDER = 'reject_sales_order', _('Can reject sales order')
    ISSUE_SALES_ORDER = 'issue_sales_order', _('Can issue sales order')
    FULFILL_SALES_ORDER = 'fulfill_sales_order', _('Can fulfill sales order')
    CANCEL_SALES_ORDER = 'cancel_sales_order', _('Can cancel sales order')
    VIEW_SALES_ORDER_HISTORY = 'view_sales_order_history', _('Can view sales order history')
    EDIT_SALES_ORDER_DETAILS = 'edit_sales_order_details', _('Can edit sales order details')
    ASSIGN_SALES_ORDER_TO_CUSTOMER = 'assign_sales_order_to_customer', _('Can assign sales order to customer')
    CHANGE_CUSTOMER_FOR_SALES_ORDER = 'change_customer_for_sales_order', _('Can change customer for sales order')
    ADD_NOTES_TO_SALES_ORDER = 'add_notes_to_sales_order', _('Can add notes to sales order')
    ATTACH_DOCUMENTS_TO_SALES_ORDER = 'attach_documents_to_sales_order', _('Can attach documents to sales order')
    SET_SALES_ORDER_PRIORITY = 'set_sales_order_priority', _('Can set sales order priority')
    SPLIT_SALES_ORDER = 'split_sales_order', _('Can split sales order')
    MERGE_SALES_ORDERS = 'merge_sales_orders', _('Can merge sales orders')
    CREATE_SALES_ORDER_TEMPLATE = 'create_sales_order_template', _('Can create sales order template')
    USE_SALES_ORDER_TEMPLATE = 'use_sales_order_template', _('Can use sales order template')
    EXPORT_SALES_ORDERS = 'export_sales_orders', _('Can export sales orders')
    IMPORT_SALES_ORDERS = 'import_sales_orders', _('Can import sales orders')
    GENERATE_SALES_ORDER_REPORTS = 'generate_sales_order_reports', _('Can generate sales order reports')
    NOTIFY_USERS_ABOUT_SALES_ORDER_STATUS = 'notify_users_about_sales_order_status', _('Can notify users about sales order status')
    MANAGE_SALES_ORDER_SETTINGS = 'manage_sales_order_settings', _('Can manage sales order settings')

    # Stock Item Permissions
    CREATE_STOCK_ITEM = 'create_stock_item', _('Can create stock item')
    READ_STOCK_ITEM = 'read_stock_item', _('Can read stock item')
    UPDATE_STOCK_ITEM = 'update_stock_item', _('Can update stock item')
    DELETE_STOCK_ITEM = 'delete_stock_item', _('Can delete stock item')
    APPROVE_STOCK_ITEM = 'approve_stock_item', _('Can approve stock item')
    REJECT_STOCK_ITEM = 'reject_stock_item', _('Can reject stock item')
    ISSUE_STOCK_ITEM = 'issue_stock_item', _('Can issue stock item')
    RECEIVE_STOCK_ITEM = 'receive_stock_item', _('Can receive stock item')
    TRANSFER_STOCK_ITEM = 'transfer_stock_item', _('Can transfer stock item')
    ADJUST_STOCK_ITEM_QUANTITY = 'adjust_stock_item_quantity', _('Can adjust stock item quantity')
    VIEW_STOCK_ITEM_HISTORY = 'view_stock_item_history', _('Can view stock item history')
    EDIT_STOCK_ITEM_DETAILS = 'edit_stock_item_details', _('Can edit stock item details')
    ASSIGN_STOCK_ITEM_TO_CATEGORY = 'assign_stock_item_to_category', _('Can assign stock item to category')
    CHANGE_STOCK_ITEM_CATEGORY = 'change_stock_item_category', _('Can change stock item category')
    ADD_NOTES_TO_STOCK_ITEM = 'add_notes_to_stock_item', _('Can add notes to stock item')
    ATTACH_DOCUMENTS_TO_STOCK_ITEM = 'attach_documents_to_stock_item', _('Can attach documents to stock item')
    SET_STOCK_ITEM_REORDER_LEVEL = 'set_stock_item_reorder_level', _('Can set stock item reorder level')
    SET_STOCK_ITEM_PRIORITY = 'set_stock_item_priority', _('Can set stock item priority')
    CREATE_STOCK_ITEM_TEMPLATE = 'create_stock_item_template', _('Can create stock item template')
    USE_STOCK_ITEM_TEMPLATE = 'use_stock_item_template', _('Can use stock item template')
    EXPORT_STOCK_ITEMS = 'export_stock_items', _('Can export stock items')
    IMPORT_STOCK_ITEMS = 'import_stock_items', _('Can import stock items')
    GENERATE_STOCK_ITEM_REPORTS = 'generate_stock_item_reports', _('Can generate stock item reports')
    NOTIFY_USERS_ABOUT_STOCK_ITEM_STATUS = 'notify_users_about_stock_item_status', _('Can notify users about stock item status')
    MANAGE_STOCK_ITEM_SETTINGS = 'manage_stock_item_settings', _('Can manage stock item settings')

class CustomUserPermission(models.Model):
    codename = models.CharField(
        max_length=100,
        unique=True,
        choices=CombinedPermissions.choices,
        help_text="Technical permission identifier"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable permission name (auto-populated)"
    )
    description = models.TextField(help_text="Detailed explanation of permission scope",blank=True,null=True)
    category = models.ForeignKey(
        PermissionCategory,
        on_delete=models.CASCADE,
        related_name='permissions',
        help_text="Organizational grouping for permissions"
    )

    class Meta:
        indexes = [
            models.Index(fields=['codename']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'codename'],
                name='unique_permission_per_category'
            )
        ]
        ordering = ['category', 'codename']


    def __str__(self):
        return f"{self.category.name.replace(' ', '_')}.{self.codename}"

    def save(self, *args, **kwargs):
        """Auto-populate name from CombinedPermissions choice label"""
        if not self.name:
            # Get human-readable name from TextChoices
            self.name = CombinedPermissions(self.codename).label
        super().save(*args, **kwargs)


