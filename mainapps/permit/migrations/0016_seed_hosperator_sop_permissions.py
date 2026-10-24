from django.db import migrations


SOP_PERMISSIONS = (
    (
        "hosperator.sop.read",
        "View Hosperator operating standards",
        "View published and draft standard operating procedures permitted for the workspace.",
    ),
    (
        "hosperator.sop.manage",
        "Manage Hosperator operating standards",
        "Create and maintain draft standard operating procedures and their steps.",
    ),
    (
        "hosperator.sop.publish",
        "Publish Hosperator operating standards",
        "Publish or retire standard operating procedure revisions with an audit trail.",
    ),
)


def seed_sop_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Standard Operating Procedures",
        defaults={
            "description": "Hosperator permissions for governed operating standards and procedure revisions",
        },
    )
    for codename, name, description in SOP_PERMISSIONS:
        CustomUserPermission.objects.get_or_create(
            platform="hosperator",
            codename=codename,
            defaults={
                "category": category,
                "name": name,
                "description": description,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("permit", "0015_seed_hosperator_device_binding_permission")]

    operations = [migrations.RunPython(seed_sop_permissions, migrations.RunPython.noop)]
