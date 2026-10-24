from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profile", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmmodel",
            name="base_url",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="profileagent",
            name="base_url",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
