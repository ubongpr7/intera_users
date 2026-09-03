from __future__ import annotations

from dataclasses import dataclass

from mainapps.permit.models import CombinedPermissions, CustomUserPermission, PlatformChoices

from .models import CompanyProfile, StaffGroup, StaffRole


@dataclass(frozen=True)
class StaffAccessPreset:
    name: str
    description: str
    permissions: tuple[str, ...]
    permission_prefixes: tuple[str, ...] = ()
    all_permissions: bool = False


def get_default_staff_access_presets(platform=PlatformChoices.INTERA_IMS) -> list[StaffAccessPreset]:
    if platform == PlatformChoices.HOSPERATOR:
        return [
            StaffAccessPreset(
                name="Hosperator Administrator",
                description="Full access to Hosperator hospital management and operational workflows",
                permissions=(),
                all_permissions=True,
            ),
            StaffAccessPreset(
                name="Hosperator Clinical Manager",
                description="Manage clinical documentation, diagnostics, care workflows, and inpatient operations",
                permissions=("hosperator.organization.read", "hosperator.reporting.read"),
                permission_prefixes=(
                    "hosperator.patient.",
                    "hosperator.appointment.",
                    "hosperator.encounter.",
                    "hosperator.order.",
                    "hosperator.task.",
                    "hosperator.clinical.",
                    "hosperator.diagnostic.",
                    "hosperator.inpatient.",
                    "hosperator.queue.",
                ),
            ),
            StaffAccessPreset(
                name="Hosperator Receptionist",
                description="Register patients, manage appointments, and operate front-desk queues",
                permissions=(
                    "hosperator.organization.read",
                    "hosperator.patient.read",
                    "hosperator.patient.write",
                    "hosperator.appointment.read",
                    "hosperator.appointment.write",
                    "hosperator.queue.read",
                    "hosperator.queue.write",
                    "hosperator.queue.complete",
                ),
            ),
            StaffAccessPreset(
                name="Hosperator Nurse",
                description="Record nursing observations and operate assigned patient-care workflows",
                permissions=(
                    "hosperator.organization.read",
                    "hosperator.patient.read",
                    "hosperator.appointment.read",
                    "hosperator.encounter.read",
                    "hosperator.encounter.write",
                    "hosperator.order.read",
                    "hosperator.order.write",
                    "hosperator.task.read",
                    "hosperator.task.write",
                    "hosperator.task.complete",
                    "hosperator.clinical.allergy.read",
                    "hosperator.clinical.allergy.write",
                    "hosperator.clinical.finding.read",
                    "hosperator.clinical.finding.write",
                    "hosperator.clinical.note.read",
                    "hosperator.clinical.note.write",
                    "hosperator.clinical.vital.read",
                    "hosperator.clinical.vital.write",
                    "hosperator.inpatient.read",
                    "hosperator.inpatient.write",
                    "hosperator.queue.read",
                    "hosperator.queue.write",
                    "hosperator.queue.complete",
                ),
            ),
            StaffAccessPreset(
                name="Hosperator Laboratory Staff",
                description="Process diagnostic requests, specimens, and result release workflows",
                permissions=(
                    "hosperator.organization.read",
                    "hosperator.patient.read",
                    "hosperator.encounter.read",
                    "hosperator.order.read",
                    "hosperator.reporting.read",
                ),
                permission_prefixes=("hosperator.diagnostic.",),
            ),
            StaffAccessPreset(
                name="Hosperator Billing Officer",
                description="Manage hospital charges, invoices, payments, cashier shifts, and payer claims",
                permissions=(
                    "hosperator.organization.read",
                    "hosperator.patient.read",
                    "hosperator.encounter.read",
                    "hosperator.service_catalog.read",
                    "hosperator.reporting.read",
                ),
                permission_prefixes=(
                    "hosperator.charge.",
                    "hosperator.invoice.",
                    "hosperator.payment.",
                    "hosperator.cashier_shift.",
                    "hosperator.claims.",
                ),
            ),
            StaffAccessPreset(
                name="Hosperator Viewer",
                description="Read-only access to Hosperator records and operational reports",
                permissions=("hosperator.organization.read", "hosperator.reporting.read"),
                permission_prefixes=(
                    "hosperator.patient.",
                    "hosperator.appointment.read",
                    "hosperator.encounter.read",
                    "hosperator.order.read",
                    "hosperator.task.read",
                    "hosperator.clinical.",
                    "hosperator.diagnostic.",
                    "hosperator.inpatient.read",
                    "hosperator.queue.read",
                    "hosperator.service_catalog.read",
                    "hosperator.charge.read",
                    "hosperator.invoice.read",
                    "hosperator.payment.read",
                    "hosperator.cashier_shift.read",
                    "hosperator.claims.read",
                ),
            ),
        ]

    return [
        StaffAccessPreset(
            name="IMS Administrator",
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
                CombinedPermissions.VIEW_AUDIT_TRAIL,
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
            name="IMS POS Manager",
            description="Manage POS operations, remittances, reports, and POS setup",
            permissions=(
                CombinedPermissions.READ_POS,
                CombinedPermissions.OPERATE_POS,
                CombinedPermissions.MANAGE_POS_SETTINGS,
                CombinedPermissions.MANAGE_POS_REMITTANCES,
                CombinedPermissions.VIEW_POS_REPORTS,
                CombinedPermissions.VIEW_DASHBOARD_REPORTS,
                CombinedPermissions.VIEW_AUDIT_TRAIL,
            ),
        ),
        StaffAccessPreset(
            name="IMS Cashier",
            description="Run cashier sessions, cart operations, checkout, and customer assignment",
            permissions=(
                CombinedPermissions.READ_POS,
                CombinedPermissions.OPERATE_POS,
            ),
        ),
        StaffAccessPreset(
            name="IMS Back Office Manager",
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
                CombinedPermissions.VIEW_AUDIT_TRAIL,
            ),
        ),
        StaffAccessPreset(
            name="IMS Inventory Manager",
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
                CombinedPermissions.VIEW_AUDIT_TRAIL,
            ),
        ),
        StaffAccessPreset(
            name="IMS Purchase Manager",
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
                CombinedPermissions.VIEW_AUDIT_TRAIL,
            ),
        ),
        StaffAccessPreset(
            name="IMS Warehouse Staff",
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
            name="IMS Viewer",
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


def _sync_presets_for_model(model_cls, platform=PlatformChoices.INTERA_IMS):
    created_count = 0
    updated_count = 0
    preset_names: list[str] = []

    for preset in get_default_staff_access_presets(platform):
        available_permissions = list(CustomUserPermission.objects.filter(platform=platform))
        if preset.all_permissions:
            permissions = available_permissions
        else:
            permissions = [
                permission
                for permission in available_permissions
                if permission.codename in preset.permissions
                or any(permission.codename.startswith(prefix) for prefix in preset.permission_prefixes)
            ]
        obj, created = model_cls.objects.get_or_create(
            name=preset.name,
            platform=platform,
            is_system=True,
            profile=None,
            defaults={"description": preset.description, "created_by": None},
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


def sync_default_staff_roles(profile: CompanyProfile, platform=PlatformChoices.INTERA_IMS):
    del profile
    return sync_system_staff_roles(platform=platform)


def sync_default_staff_groups(profile: CompanyProfile, platform=PlatformChoices.INTERA_IMS):
    del profile
    return sync_system_staff_groups(platform=platform)


def populate_default_staff_access(profile: CompanyProfile, platform=PlatformChoices.INTERA_IMS):
    roles = sync_system_staff_roles(platform=platform)
    groups = sync_system_staff_groups(platform=platform)
    return {
        "profile_id": str(profile.id),
        "profile_name": profile.name,
        "platform": platform,
        "roles": roles,
        "groups": groups,
    }


def sync_system_staff_roles(platform=PlatformChoices.INTERA_IMS):
    return _sync_presets_for_model(StaffRole, platform=platform)


def sync_system_staff_groups(platform=PlatformChoices.INTERA_IMS):
    return _sync_presets_for_model(StaffGroup, platform=platform)
