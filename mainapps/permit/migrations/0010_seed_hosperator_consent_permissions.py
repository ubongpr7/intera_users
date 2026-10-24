from django.db import migrations


CONSENT_PERMISSIONS = (
    ("hosperator.consent.read", "View consent, document, and disclosure records"),
    ("hosperator.consent.configure", "Configure consent definitions and document retention policies"),
    ("hosperator.consent.write", "Create and update consent, document, and disclosure workflows"),
    ("hosperator.consent.manage", "Manage consent and document configuration records"),
)


def seed_consent_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Consent and Documents",
        defaults={"description": "Hosperator consent and controlled-document permissions"},
    )
    for codename, description in CONSENT_PERMISSIONS:
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
        ("permit", "0009_seed_hosperator_inpatient_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_consent_permissions, migrations.RunPython.noop),
    ]
