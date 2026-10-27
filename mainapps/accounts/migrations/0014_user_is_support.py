from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_user_profile_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_support",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Platform support account allowed to use the support portal without admin access.",
            ),
        ),
    ]
