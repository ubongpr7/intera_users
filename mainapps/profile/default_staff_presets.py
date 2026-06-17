from __future__ import annotations

from dataclasses import dataclass

from mainapps.permit.models import CombinedPermissions, CustomUserPermission

from .models import CompanyProfile, StaffGroup, StaffRole


@dataclass(frozen=True)
class StaffAccessPreset:
    name: str
    description: str
    permissions: tuple[str, ...]


def get_default_staff_access_presets() -> list[StaffAccessPreset]:
    return [
        StaffAccessPreset(
            name="Administrator",
            description="Full access to all inventory, POS, AI, and company management features",
            permissions=(
                CombinedPermissions.CREATE_AGENT,
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.UPDATE_AGENT,
                CombinedPermissions.DELETE_AGENT,
                CombinedPermissions.MANAGE_AGENT_SETTINGS,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.VIEW_AGENT_ACTIVITY,
                CombinedPermissions.READ_POS,
                CombinedPermissions.OPERATE_POS,
                CombinedPermissions.MANAGE_POS_SETTINGS,
                CombinedPermissions.MANAGE_POS_REMITTANCES,
                CombinedPermissions.VIEW_POS_REPORTS,
                CombinedPermissions.CREATE_INVENTORY,
                CombinedPermissions.READ_INVENTORY,
                CombinedPermissions.UPDATE_INVENTORY,
                CombinedPermissions.DELETE_INVENTORY,
                CombinedPermissions.APPROVE_INVENTORY,
                CombinedPermissions.VIEW_INVENTORY_REPORTS,
                CombinedPermissions.MANAGE_INVENTORY_SETTINGS,
                CombinedPermissions.CREATE_PURCHASE_ORDER,
                CombinedPermissions.READ_PURCHASE_ORDER,
                CombinedPermissions.UPDATE_PURCHASE_ORDER,
                CombinedPermissions.DELETE_PURCHASE_ORDER,
                CombinedPermissions.APPROVE_PURCHASE_ORDER,
                CombinedPermissions.ISSUE_PURCHASE_ORDER,
                CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                CombinedPermissions.CREATE_STOCK_ITEM,
                CombinedPermissions.READ_STOCK_ITEM,
                CombinedPermissions.UPDATE_STOCK_ITEM,
                CombinedPermissions.DELETE_STOCK_ITEM,
                CombinedPermissions.TRANSFER_STOCK_ITEM,
                CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
            ),
        ),
        StaffAccessPreset(
            name="POS Manager",
            description="Manage POS operations, remittances, reports, and POS setup",
            permissions=(
                CombinedPermissions.READ_POS,
                CombinedPermissions.OPERATE_POS,
                CombinedPermissions.MANAGE_POS_SETTINGS,
                CombinedPermissions.MANAGE_POS_REMITTANCES,
                CombinedPermissions.VIEW_POS_REPORTS,
                CombinedPermissions.VIEW_DASHBOARD_REPORTS,
            ),
        ),
        StaffAccessPreset(
            name="Cashier",
            description="Run cashier sessions, cart operations, checkout, and customer assignment",
            permissions=(
                CombinedPermissions.READ_POS,
                CombinedPermissions.OPERATE_POS,
            ),
        ),
        StaffAccessPreset(
            name="BO Manager",
            description="Run back-office operations across inventory, purchasing, stock control, and reporting",
            permissions=(
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.VIEW_AGENT_ACTIVITY,
                CombinedPermissions.CREATE_INVENTORY,
                CombinedPermissions.READ_INVENTORY,
                CombinedPermissions.UPDATE_INVENTORY,
                CombinedPermissions.VIEW_INVENTORY_REPORTS,
                CombinedPermissions.CREATE_PURCHASE_ORDER,
                CombinedPermissions.READ_PURCHASE_ORDER,
                CombinedPermissions.UPDATE_PURCHASE_ORDER,
                CombinedPermissions.APPROVE_PURCHASE_ORDER,
                CombinedPermissions.ISSUE_PURCHASE_ORDER,
                CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                CombinedPermissions.CREATE_STOCK_ITEM,
                CombinedPermissions.READ_STOCK_ITEM,
                CombinedPermissions.UPDATE_STOCK_ITEM,
                CombinedPermissions.TRANSFER_STOCK_ITEM,
                CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
                CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
                CombinedPermissions.READ_STOCK_LOCATION,
                CombinedPermissions.CREATE_STOCK_LOCATION,
                CombinedPermissions.UPDATE_STOCK_LOCATION,
                CombinedPermissions.VIEW_DASHBOARD_REPORTS,
            ),
        ),
        StaffAccessPreset(
            name="Inventory Manager",
            description="Manage inventory items and stock levels",
            permissions=(
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.VIEW_AGENT_ACTIVITY,
                CombinedPermissions.CREATE_INVENTORY,
                CombinedPermissions.READ_INVENTORY,
                CombinedPermissions.UPDATE_INVENTORY,
                CombinedPermissions.CREATE_STOCK_ITEM,
                CombinedPermissions.READ_STOCK_ITEM,
                CombinedPermissions.UPDATE_STOCK_ITEM,
                CombinedPermissions.TRANSFER_STOCK_ITEM,
                CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
                CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
            ),
        ),
        StaffAccessPreset(
            name="Purchase Manager",
            description="Manage purchase orders and supplier relationships",
            permissions=(
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.VIEW_AGENT_ACTIVITY,
                CombinedPermissions.CREATE_PURCHASE_ORDER,
                CombinedPermissions.READ_PURCHASE_ORDER,
                CombinedPermissions.UPDATE_PURCHASE_ORDER,
                CombinedPermissions.APPROVE_PURCHASE_ORDER,
                CombinedPermissions.ISSUE_PURCHASE_ORDER,
                CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                CombinedPermissions.CREATE_PURCHASE_ORDER_LINE_ITEM,
                CombinedPermissions.READ_PURCHASE_ORDER_LINE_ITEM,
                CombinedPermissions.UPDATE_PURCHASE_ORDER_LINE_ITEM,
            ),
        ),
        StaffAccessPreset(
            name="Warehouse Staff",
            description="Basic warehouse operations and stock handling",
            permissions=(
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.READ_INVENTORY,
                CombinedPermissions.READ_STOCK_ITEM,
                CombinedPermissions.UPDATE_STOCK_ITEM,
                CombinedPermissions.TRANSFER_STOCK_ITEM,
                CombinedPermissions.RECEIVE_PURCHASE_ORDER,
                CombinedPermissions.READ_STOCK_LOCATION,
            ),
        ),
        StaffAccessPreset(
            name="Viewer",
            description="Read-only access to inventory and reports",
            permissions=(
                CombinedPermissions.READ_AGENT,
                CombinedPermissions.INTERACT_WITH_AGENT,
                CombinedPermissions.VIEW_AGENT_ACTIVITY,
                CombinedPermissions.READ_INVENTORY,
                CombinedPermissions.READ_STOCK_ITEM,
                CombinedPermissions.READ_PURCHASE_ORDER,
                CombinedPermissions.READ_STOCK_LOCATION,
                CombinedPermissions.VIEW_INVENTORY_REPORTS,
                CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
            ),
        ),
    ]


def _sync_presets_for_model(profile: CompanyProfile, model_cls):
    created_count = 0
    updated_count = 0
    preset_names: list[str] = []

    for preset in get_default_staff_access_presets():
        permissions = CustomUserPermission.objects.filter(codename__in=preset.permissions)
        obj, created = model_cls.objects.get_or_create(
            name=preset.name,
            profile=profile,
            defaults={"description": preset.description},
        )

        fields_to_update: list[str] = []
        if obj.description != preset.description:
            obj.description = preset.description
            fields_to_update.append("description")
        if fields_to_update:
            obj.save(update_fields=fields_to_update)

        obj.permissions.set(permissions)
        preset_names.append(preset.name)

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "preset_names": preset_names,
    }


def sync_default_staff_roles(profile: CompanyProfile):
    return _sync_presets_for_model(profile, StaffRole)


def sync_default_staff_groups(profile: CompanyProfile):
    return _sync_presets_for_model(profile, StaffGroup)


def populate_default_staff_access(profile: CompanyProfile):
    roles = sync_default_staff_roles(profile)
    groups = sync_default_staff_groups(profile)
    return {
        "profile_id": str(profile.id),
        "profile_name": profile.name,
        "roles": roles,
        "groups": groups,
    }
