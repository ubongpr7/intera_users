from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_user_referral_commission_rate")]

    operations = [
        migrations.CreateModel(
            name="PlatformStaffInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("revoked", "Revoked"), ("expired", "Expired")], db_index=True, default="pending", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accepted_platform_staff_invitations", to="accounts.user")),
                ("invited_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="platform_staff_invitations", to="accounts.user")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="platformstaffinvitation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("email",), name="accounts_one_pending_platform_staff_invite"),
        ),
    ]
