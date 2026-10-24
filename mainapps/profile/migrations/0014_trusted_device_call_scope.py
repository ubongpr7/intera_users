from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("profile", "0013_trusted_workspace_device"),
    ]

    operations = [
        migrations.AddField(
            model_name="trustedworkspacedevice",
            name="care_site_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text="Opaque Hosperator Core care-site scope for this device binding.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trustedworkspacedevice",
            name="last_seen_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="trusted_workspace_devices_seen",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
