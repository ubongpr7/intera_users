from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_platformstaffinvitation"),
    ]

    operations = [
        migrations.AddField(
            model_name="affiliatepartner",
            name="email",
            field=models.EmailField(blank=True, db_index=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="affiliatepartner",
            name="account_user",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="affiliate_partner_account", to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name="AffiliatePartnerInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("revoked", "Revoked"), ("expired", "Expired")], db_index=True, default="pending", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accepted_affiliate_invitations", to=settings.AUTH_USER_MODEL)),
                ("invited_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="affiliate_partner_invitations", to=settings.AUTH_USER_MODEL)),
                ("partner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="accounts.affiliatepartner")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="affiliatepartnerinvitation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("partner",), name="accounts_one_pending_affiliate_invite"),
        ),
    ]
