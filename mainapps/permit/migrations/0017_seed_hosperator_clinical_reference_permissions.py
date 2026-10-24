from django.db import migrations


REFERENCE_PERMISSIONS = (
    (
        "hosperator.clinical.reference.read",
        "View Hosperator clinical reference codes",
        "Search approved clinical terminology used to prefill structured records.",
    ),
    (
        "hosperator.clinical.reference.manage",
        "Manage Hosperator clinical reference codes",
        "Create, update, and deactivate tenant-approved clinical terminology.",
    ),
)


def seed_reference_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Clinical Documentation",
        defaults={"description": "Hosperator clinical documentation permissions"},
    )
    for codename, name, description in REFERENCE_PERMISSIONS:
        CustomUserPermission.objects.get_or_create(
            platform="hosperator",
            codename=codename,
            defaults={"category": category, "name": name, "description": description},
        )


class Migration(migrations.Migration):
    dependencies = [("permit", "0016_seed_hosperator_sop_permissions")]

    operations = [migrations.RunPython(seed_reference_permissions, migrations.RunPython.noop)]
