from django.db import migrations


def seed_sop_acknowledgement_permission(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Standard Operating Procedures",
        defaults={
            "description": "Hosperator permissions for governed operating standards and procedure revisions",
        },
    )
    CustomUserPermission.objects.get_or_create(
        platform="hosperator",
        codename="hosperator.sop.acknowledge",
        defaults={
            "category": category,
            "name": "Acknowledge Hosperator operating standards",
            "description": "Complete SOP acknowledgements assigned to the current staff member.",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("permit", "0017_seed_hosperator_clinical_reference_permissions")]

    operations = [migrations.RunPython(seed_sop_acknowledgement_permission, migrations.RunPython.noop)]
