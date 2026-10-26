from django.db import migrations, models


def mark_existing_affiliate_accounts(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    AffiliatePartner = apps.get_model('accounts', 'AffiliatePartner')
    account_user_ids = AffiliatePartner.objects.exclude(account_user_id=None).values_list('account_user_id', flat=True)
    User.objects.filter(id__in=account_user_ids).update(is_affiliate_marketer=True)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0011_alter_user_sex'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_affiliate_marketer',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Affiliate partner account restricted from normal workspace and billing operations.',
            ),
        ),
        migrations.RunPython(mark_existing_affiliate_accounts, migrations.RunPython.noop),
    ]
