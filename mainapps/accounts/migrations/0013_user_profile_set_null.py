from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_user_is_affiliate_marketer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="staff",
                to="profile.companyprofile",
            ),
        ),
    ]
