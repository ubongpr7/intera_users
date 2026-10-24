from django.db import migrations, models

from mainapps.permit.models import CombinedPermissions


PERMISSIONS = (
    ("view_audit_trail", "Can view workspace audit trail"),
)


def seed_audit_trail_permission(apps, schema_editor):
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    PermissionCategory = apps.get_model("permit", "PermissionCategory")

    category, _ = PermissionCategory.objects.get_or_create(
        name="Company",
        defaults={
            "description": "Company and workspace administration permissions",
            "icon": "building",
            "service": "services",
        },
    )

    for codename, label in PERMISSIONS:
        CustomUserPermission.objects.get_or_create(
            codename=codename,
            defaults={"name": label, "category_id": category.id},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("permit", "0005_seed_support_access_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuserpermission",
            name="codename",
            field=models.CharField(
                choices=CombinedPermissions.choices,
                help_text="Technical permission identifier",
                max_length=100,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_audit_trail_permission, migrations.RunPython.noop),
    ]
