import secrets

import mainapps.profile.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _generate_code():
    return secrets.token_urlsafe(24)[:32]


def populate_support_access_invitation_codes(apps, schema_editor):
    SupportAccessGrant = apps.get_model("profile", "SupportAccessGrant")

    for grant in SupportAccessGrant.objects.filter(invitation_code__isnull=True):
        code = _generate_code()
        while SupportAccessGrant.objects.filter(invitation_code=code).exists():
            code = _generate_code()
        grant.invitation_code = code
        grant.save(update_fields=["invitation_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("profile", "0004_supportaccessgrant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="supportaccessgrant",
            name="accepted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="support_access_grants_accepted",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="supportaccessgrant",
            name="invitation_code",
            field=models.CharField(blank=True, max_length=48, null=True),
        ),
        migrations.AddField(
            model_name="supportaccessgrant",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="supportaccessgrant",
            name="grantee_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="support_access_grants_received",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="supportaccessgrant",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("active", "Active"),
                    ("declined", "Declined"),
                    ("expired", "Expired"),
                    ("revoked", "Revoked"),
                    ("consumed", "Consumed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_support_access_invitation_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supportaccessgrant",
            name="invitation_code",
            field=models.CharField(
                default=mainapps.profile.models.generate_support_access_invitation_code,
                max_length=48,
                unique=True,
            ),
        ),
    ]
