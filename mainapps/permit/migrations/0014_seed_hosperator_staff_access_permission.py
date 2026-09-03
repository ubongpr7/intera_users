from django.db import migrations


def seed_staff_access_permission(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Organization",
        defaults={"description": "Hosperator organization and access-management permissions"},
    )
    CustomUserPermission.objects.get_or_create(
        platform="hosperator",
        codename="hosperator.staff_access.manage",
        defaults={
            "category": category,
            "name": "Manage Hosperator staff access",
            "description": "Invite staff and assign Hosperator roles, groups, and permissions",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("permit", "0013_seed_hosperator_operational_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_staff_access_permission, migrations.RunPython.noop),
    ]
