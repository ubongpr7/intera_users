from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalConsent",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "consent_type",
                    models.CharField(
                        choices=[("terms", "Terms and Conditions"), ("privacy", "Privacy Policy")],
                        max_length=16,
                    ),
                ),
                ("policy_version", models.CharField(max_length=64)),
                ("accepted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=1024)),
                ("source", models.CharField(default="signup", max_length=32)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="legal_consents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user", "consent_type"], name="accounts_le_user_id_8dc874_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "consent_type", "policy_version"),
                        name="unique_user_legal_consent_version",
                    )
                ],
            },
        ),
    ]
