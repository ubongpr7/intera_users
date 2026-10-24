from django.db import migrations


INPATIENT_PERMISSIONS = (
    ("hosperator.inpatient.read", "View inpatient capacity and workflow records"),
    ("hosperator.inpatient.configure", "Configure wards, beds, theatres, and controlled capacity values"),
    ("hosperator.inpatient.write", "Create and update inpatient operational workflows"),
    ("hosperator.inpatient.manage", "Manage inpatient operational records"),
)


def seed_inpatient_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Inpatient Operations",
        defaults={"description": "Hosperator inpatient capacity and workflow permissions"},
    )
    for codename, description in INPATIENT_PERMISSIONS:
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
        ("permit", "0008_seed_hosperator_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_inpatient_permissions, migrations.RunPython.noop),
    ]
