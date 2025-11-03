# Generated manually to add missing balance fields

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0007_bankaccount_gl_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankaccount',
            name='current_balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Current book balance',
                max_digits=12
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='reconciled_balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Last reconciled balance',
                max_digits=12
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='last_reconciled_date',
            field=models.DateField(
                blank=True,
                help_text='Date of last successful reconciliation',
                null=True
            ),
        ),
        migrations.AddIndex(
            model_name='bankaccount',
            index=models.Index(fields=['last_reconciled_date'], name='accounting__last_re_idx'),
        ),
    ]
