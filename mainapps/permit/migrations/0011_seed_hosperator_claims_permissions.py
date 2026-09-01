from django.db import migrations


CLAIMS_PERMISSIONS = (
    ("hosperator.claims.read", "View payer, coverage, claim, and remittance records"),
    ("hosperator.claims.configure", "Configure payer plans and response-code vocabularies"),
    ("hosperator.claims.write", "Create and process coverage, authorization, claim, and remittance workflows"),
    ("hosperator.claims.manage", "Manage payer-claims configuration and irreversible financial actions"),
)


def seed_claims_permissions(apps, schema_editor):
    PermissionCategory = apps.get_model("permit", "PermissionCategory")
    CustomUserPermission = apps.get_model("permit", "CustomUserPermission")
    category, _ = PermissionCategory.objects.get_or_create(
        platform="hosperator",
        name="Payer Claims",
        defaults={"description": "Hosperator payer, claims, and remittance permissions"},
    )
    for codename, description in CLAIMS_PERMISSIONS:
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
        ("permit", "0010_seed_hosperator_consent_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_claims_permissions, migrations.RunPython.noop),
    ]
