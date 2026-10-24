from django.db import migrations


ADDITIONAL_HOSPERATOR_PERMISSIONS = {
    "Clinical Documentation": (
        ("hosperator.clinical.allergy.read", "View patient allergy records"),
        ("hosperator.clinical.allergy.write", "Create and update patient allergy records"),
        ("hosperator.clinical.finding.read", "View clinical findings"),
        ("hosperator.clinical.finding.write", "Create and update clinical findings"),
        ("hosperator.clinical.note.read", "View clinical notes"),
        ("hosperator.clinical.note.write", "Create and update clinical notes"),
        ("hosperator.clinical.note.sign", "Sign clinical notes"),
        ("hosperator.clinical.note.amend", "Amend signed clinical notes with an audit trail"),
        ("hosperator.clinical.template.read", "View clinical documentation templates"),
        ("hosperator.clinical.template.manage", "Manage clinical documentation templates"),
        ("hosperator.clinical.vital.read", "View patient vital observations"),
        ("hosperator.clinical.vital.write", "Record patient vital observations"),
    ),
    "Diagnostic Workflow": (
        ("hosperator.diagnostic.service_catalog.read", "View diagnostic service catalogue"),
        ("hosperator.diagnostic.service_catalog.manage", "Manage diagnostic service catalogue"),
        ("hosperator.diagnostic.request.read", "View diagnostic requests"),
        ("hosperator.diagnostic.request.accept", "Accept diagnostic requests"),
        ("hosperator.diagnostic.request.cancel", "Cancel diagnostic requests"),
        ("hosperator.diagnostic.specimen.read", "View diagnostic specimens"),
        ("hosperator.diagnostic.specimen.write", "Create and update diagnostic specimens"),
        ("hosperator.diagnostic.specimen.collect", "Collect diagnostic specimens"),
        ("hosperator.diagnostic.specimen.receive", "Receive diagnostic specimens"),
        ("hosperator.diagnostic.specimen.reject", "Reject diagnostic specimens"),
        ("hosperator.diagnostic.result.read", "View diagnostic results"),
        ("hosperator.diagnostic.result.write", "Enter diagnostic results"),
        ("hosperator.diagnostic.result.validate", "Validate diagnostic results"),
        ("hosperator.diagnostic.result.release", "Release diagnostic results"),
        ("hosperator.diagnostic.result.correct", "Correct released diagnostic results with an audit trail"),
        ("hosperator.diagnostic.result.review", "Review diagnostic results"),
    ),
    "Revenue and Billing": (
        ("hosperator.service_catalog.read", "View hospital service catalogue"),
        ("hosperator.service_catalog.manage", "Manage hospital service catalogue"),
        ("hosperator.charge.read", "View patient charge events"),
        ("hosperator.charge.write", "Create and update patient charge events"),
        ("hosperator.charge.approve", "Approve patient charge events"),
        ("hosperator.charge.cancel", "Cancel patient charge events"),
        ("hosperator.charge.prepare_claim", "Prepare patient charges for claims"),
        ("hosperator.invoice.read", "View invoices"),
        ("hosperator.invoice.write", "Create and update invoices"),
        ("hosperator.invoice.issue", "Issue invoices"),
        ("hosperator.invoice.void", "Void invoices with an audit trail"),
        ("hosperator.invoice.credit", "Issue invoice credit notes"),
        ("hosperator.payment.read", "View payment records"),
        ("hosperator.payment.capture", "Capture payments"),
        ("hosperator.payment.refund", "Refund payments"),
        ("hosperator.cashier_shift.read", "View cashier shifts"),
        ("hosperator.cashier_shift.open", "Open cashier shifts"),
        ("hosperator.cashier_shift.close", "Close cashier shifts"),
    ),
    "Patient Operations": (
        ("hosperator.patient.merge", "Merge duplicate patient operational records"),
        ("hosperator.queue.read", "View patient operational queues"),
        ("hosperator.queue.write", "Create and update queue entries"),
        ("hosperator.queue.complete", "Complete queue entries"),
        ("hosperator.queue.manage", "Manage operational queue configuration"),
        ("hosperator.pharmacy_fulfillment.read", "View pharmacy fulfilment requests"),
        ("hosperator.pharmacy_fulfillment.write", "Create pharmacy fulfilment requests"),
        ("hosperator.pharmacy_fulfillment.manage", "Manage pharmacy fulfilment requests"),
        ("hosperator.sync.read", "View operational synchronization state"),
        ("hosperator.sync.manage", "Manage operational synchronization recovery"),
    ),
    "Reporting": (
        ("hosperator.reporting.read", "View Hosperator operational reports"),
    ),
}


def seed_operational_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    for category_name, permissions in ADDITIONAL_HOSPERATOR_PERMISSIONS.items():
        category, _ = PermissionCategory.objects.get_or_create(
            platform="hosperator",
            name=category_name,
            defaults={"description": f"Hosperator {category_name.lower()} permissions"},
        )
        for codename, description in permissions:
            CustomUserPermission.objects.get_or_create(
                platform="hosperator",
                codename=codename,
                defaults={
                    "category": category,
                    "name": description,
                    "description": description,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("permit", "0012_seed_hosperator_integration_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_operational_permissions, migrations.RunPython.noop),
    ]
