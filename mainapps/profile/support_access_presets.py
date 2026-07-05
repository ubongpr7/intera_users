from __future__ import annotations

from dataclasses import dataclass

from mainapps.permit.models import CombinedPermissions


@dataclass(frozen=True)
class SupportAccessPreset:
    key: str
    name: str
    description: str
    permissions: tuple[str, ...]


SUPPORT_ACCESS_PRESETS: tuple[SupportAccessPreset, ...] = (
    SupportAccessPreset(
        key="support_readonly",
        name="Support Readonly",
        description="Inspect workspace configuration and operational state without mutating records.",
        permissions=(
            CombinedPermissions.READ_COMPANY,
            CombinedPermissions.READ_COMPANY_ADDRESS,
            CombinedPermissions.READ_AGENT,
            CombinedPermissions.VIEW_AGENT_ACTIVITY,
            CombinedPermissions.READ_INVENTORY,
            CombinedPermissions.VIEW_INVENTORY_REPORTS,
            CombinedPermissions.READ_PURCHASE_ORDER,
            CombinedPermissions.VIEW_PURCHASE_ORDER_HISTORY,
            CombinedPermissions.READ_STOCK_ITEM,
            CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
            CombinedPermissions.READ_STOCK_LOCATION,
            CombinedPermissions.READ_POS,
            CombinedPermissions.VIEW_POS_REPORTS,
        ),
    ),
    SupportAccessPreset(
        key="support_inventory_ops",
        name="Support Inventory Ops",
        description="Diagnose and correct inventory and stock flow issues without company-level administration.",
        permissions=(
            CombinedPermissions.READ_COMPANY,
            CombinedPermissions.READ_COMPANY_ADDRESS,
            CombinedPermissions.READ_AGENT,
            CombinedPermissions.INTERACT_WITH_AGENT,
            CombinedPermissions.VIEW_AGENT_ACTIVITY,
            CombinedPermissions.READ_INVENTORY,
            CombinedPermissions.UPDATE_INVENTORY,
            CombinedPermissions.VIEW_INVENTORY_REPORTS,
            CombinedPermissions.READ_PURCHASE_ORDER,
            CombinedPermissions.UPDATE_PURCHASE_ORDER,
            CombinedPermissions.ISSUE_PURCHASE_ORDER,
            CombinedPermissions.RECEIVE_PURCHASE_ORDER,
            CombinedPermissions.READ_STOCK_ITEM,
            CombinedPermissions.UPDATE_STOCK_ITEM,
            CombinedPermissions.TRANSFER_STOCK_ITEM,
            CombinedPermissions.ADJUST_STOCK_ITEM_QUANTITY,
            CombinedPermissions.VIEW_STOCK_ITEM_HISTORY,
            CombinedPermissions.READ_STOCK_LOCATION,
            CombinedPermissions.UPDATE_STOCK_LOCATION,
        ),
    ),
    SupportAccessPreset(
        key="support_pos_ops",
        name="Support POS Ops",
        description="Investigate and operate POS workflows without company-management permissions.",
        permissions=(
            CombinedPermissions.READ_COMPANY,
            CombinedPermissions.READ_COMPANY_ADDRESS,
            CombinedPermissions.READ_AGENT,
            CombinedPermissions.INTERACT_WITH_AGENT,
            CombinedPermissions.VIEW_AGENT_ACTIVITY,
            CombinedPermissions.READ_POS,
            CombinedPermissions.OPERATE_POS,
            CombinedPermissions.MANAGE_POS_SETTINGS,
            CombinedPermissions.VIEW_POS_REPORTS,
            CombinedPermissions.READ_INVENTORY,
            CombinedPermissions.READ_STOCK_ITEM,
        ),
    ),
)

SUPPORT_ACCESS_PRESET_MAP = {preset.key: preset for preset in SUPPORT_ACCESS_PRESETS}

DISALLOWED_SUPPORT_CUSTOM_PERMISSION_CODENAMES = {
    CombinedPermissions.CREATE_COMPANY,
    CombinedPermissions.UPDATE_COMPANY,
    CombinedPermissions.DELETE_COMPANY,
    CombinedPermissions.APPROVE_COMPANY,
    CombinedPermissions.REJECT_COMPANY,
    CombinedPermissions.MANAGE_COMPANY_SETTINGS,
    CombinedPermissions.CREATE_SUPPORT_ACCESS_GRANT,
    CombinedPermissions.READ_SUPPORT_ACCESS_GRANT,
    CombinedPermissions.UPDATE_SUPPORT_ACCESS_GRANT,
    CombinedPermissions.REVOKE_SUPPORT_ACCESS_GRANT,
    CombinedPermissions.APPROVE_SUPPORT_ACCESS_GRANT,
    CombinedPermissions.VIEW_SUPPORT_ACCESS_AUDIT,
}


def get_support_access_presets() -> list[SupportAccessPreset]:
    return list(SUPPORT_ACCESS_PRESETS)


def get_support_access_preset(key: str) -> SupportAccessPreset | None:
    return SUPPORT_ACCESS_PRESET_MAP.get(key)

