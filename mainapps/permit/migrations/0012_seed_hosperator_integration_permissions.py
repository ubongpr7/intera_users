from django.db import migrations


INTEGRATION_PERMISSIONS = (
    ("hosperator.integration.read", "View integration providers, contracts, connections, and automation types"),
    ("hosperator.integration.configure", "Configure integration providers, contract drafts, connections, and settings"),
    ("hosperator.integration.write", "Run integration operations and submit automation work"),
    ("hosperator.integration.manage", "Publish contracts and manage integration connection lifecycle"),
)


def seed_integration_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Integration and Automation",
        defaults={"description": "Hosperator integration and automation permissions"},
    )
    for codename, description in INTEGRATION_PERMISSIONS:
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
        ("permit", "0011_seed_hosperator_claims_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_integration_permissions, migrations.RunPython.noop),
    ]
