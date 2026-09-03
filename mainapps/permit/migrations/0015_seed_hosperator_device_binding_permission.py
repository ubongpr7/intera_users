from django.db import migrations


def seed_device_binding_permission(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Device Trust",
        defaults={"description": "Hosperator workspace device-trust permissions"},
    )
    CustomUserPermission.objects.get_or_create(
        platform="hosperator",
        codename="hosperator.device_binding.manage",
        defaults={
            "category": category,
            "name": "Manage trusted Hosperator devices",
            "description": "Bind and revoke trusted devices for a Hosperator workspace.",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("permit", "0014_seed_hosperator_staff_access_permission"),
    ]

    operations = [
        migrations.RunPython(seed_device_binding_permission, migrations.RunPython.noop),
    ]
