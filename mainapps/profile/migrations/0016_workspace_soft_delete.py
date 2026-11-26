from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profile", "0015_companyprofile_theme_logos"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("deleted", "Deleted")],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
