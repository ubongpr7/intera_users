import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("common", "0002_unit")]

    operations = [
        migrations.CreateModel(
            name="SharedAddressMigrationMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_model", models.CharField(max_length=120)),
                ("source_pk", models.CharField(max_length=64)),
                ("profile_id", models.CharField(blank=True, default="", max_length=128)),
                ("shared_address_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["source_model", "source_pk"]},
        ),
        migrations.AddConstraint(
            model_name="sharedaddressmigrationmap",
            constraint=models.UniqueConstraint(fields=["source_model", "source_pk"], name="common_shared_address_source_unique"),
        ),
    ]
