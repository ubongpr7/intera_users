import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("profile", "0012_qualify_ims_system_access_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrustedWorkspaceDevice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("platform", models.CharField(choices=[("intera_ims", "Intera IMS"), ("hosperator", "Hosperator")], db_index=True, default="hosperator", max_length=32)),
                ("device_identifier", models.CharField(db_index=True, max_length=255)),
                ("device_label", models.CharField(blank=True, max_length=255)),
                ("capabilities", models.JSONField(blank=True, default=list, help_text="Capabilities granted to this trusted device, such as staff_call.")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_revoked", models.BooleanField(db_index=True, default=False)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trusted_workspace_devices_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trusted_devices",
                        to="profile.companyprofile",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trusted_workspace_devices_revoked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["profile", "platform", "is_active"], name="profile_tru_profile_6b87e3_idx")],
                "constraints": [models.UniqueConstraint(fields=("profile", "platform", "device_identifier"), name="unique_trusted_device_per_workspace_platform")],
            },
        ),
    ]
