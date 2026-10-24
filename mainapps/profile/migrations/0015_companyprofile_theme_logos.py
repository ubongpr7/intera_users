from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profile", "0014_trusted_device_call_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="logo_light",
            field=models.ImageField(
                blank=True,
                help_text="Logo intended for light application surfaces.",
                null=True,
                upload_to="company_logos/light/%y/%m/%d/",
                verbose_name="Light mode company logo",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="logo_dark",
            field=models.ImageField(
                blank=True,
                help_text="Logo intended for dark application surfaces.",
                null=True,
                upload_to="company_logos/dark/%y/%m/%d/",
                verbose_name="Dark mode company logo",
            ),
        ),
    ]
