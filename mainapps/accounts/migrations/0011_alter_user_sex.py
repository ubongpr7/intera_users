from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_affiliatepartner_email_invitation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='sex',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('not_to_mention', 'Prefer not to mention')], default='not_to_mention', max_length=20, null=True),
        ),
    ]
