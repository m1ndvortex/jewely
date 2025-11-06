# Generated manually to add missing balance fields

from decimal import Decimal

from django.db import migrations, models


def add_balance_fields_idempotent(apps, schema_editor):
    """Add balance fields only if they don't exist"""
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            # Add current_balance if it doesn't exist
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'accounting_bank_accounts' 
                        AND column_name = 'current_balance'
                    ) THEN
                        ALTER TABLE accounting_bank_accounts 
                        ADD COLUMN current_balance NUMERIC(12, 2) DEFAULT 0.00 NOT NULL;
                        
                        COMMENT ON COLUMN accounting_bank_accounts.current_balance 
                        IS 'Current book balance';
                    END IF;
                END $$;
            """)
            
            # Add reconciled_balance if it doesn't exist
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'accounting_bank_accounts' 
                        AND column_name = 'reconciled_balance'
                    ) THEN
                        ALTER TABLE accounting_bank_accounts 
                        ADD COLUMN reconciled_balance NUMERIC(12, 2) DEFAULT 0.00 NOT NULL;
                        
                        COMMENT ON COLUMN accounting_bank_accounts.reconciled_balance 
                        IS 'Last reconciled balance';
                    END IF;
                END $$;
            """)
            
            # Add last_reconciled_date if it doesn't exist
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'accounting_bank_accounts' 
                        AND column_name = 'last_reconciled_date'
                    ) THEN
                        ALTER TABLE accounting_bank_accounts 
                        ADD COLUMN last_reconciled_date DATE NULL;
                        
                        COMMENT ON COLUMN accounting_bank_accounts.last_reconciled_date 
                        IS 'Date of last successful reconciliation';
                    END IF;
                END $$;
            """)
            
            # Add index if it doesn't exist
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = 'accounting__last_re_idx'
                    ) THEN
                        CREATE INDEX accounting__last_re_idx 
                        ON accounting_bank_accounts (last_reconciled_date);
                    END IF;
                END $$;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0007_bankaccount_gl_account'),
    ]

    operations = [
        migrations.RunPython(add_balance_fields_idempotent, migrations.RunPython.noop),
    ]
