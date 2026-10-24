from django.db import migrations


SUPPORT_ACCESS_PERMISSIONS = [
    ("create_support_access_grant", "Can create support access grants"),
    ("read_support_access_grant", "Can read support access grants"),
    ("update_support_access_grant", "Can update support access grants"),
    ("revoke_support_access_grant", "Can revoke support access grants"),
    ("approve_support_access_grant", "Can approve support access grants"),
    ("view_support_access_audit", "Can view support access audit"),
]


def seed_support_access_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")

    category, _ = PermissionCategory.objects.get_or_create(
        name="Support Access Grant",
        defaults={"description": "Support access grant related permissions"},
    )

    for codename, label in SUPPORT_ACCESS_PERMISSIONS:
        CustomUserPermission.objects.get_or_create(
            codename=codename,
            category=category,
            defaults={
                "name": label,
                "description": label,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("permit", "0004_alter_customuserpermission_codename"),
    ]

    operations = [
        migrations.RunPython(seed_support_access_permissions, migrations.RunPython.noop),
    ]

