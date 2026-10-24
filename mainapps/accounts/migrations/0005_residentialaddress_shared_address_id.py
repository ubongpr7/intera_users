from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_user_referral_code_user_referred_by_referralpayout")]
    operations = [migrations.AddField(
        model_name="residentialaddress",
        name="shared_address_id",
        field=models.UUIDField(blank=True, db_index=True, editable=False, help_text="Opaque address ID owned by the shared locations service.", null=True, verbose_name="Shared address ID"),
    )]
