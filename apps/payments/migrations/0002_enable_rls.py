# Generated migration for enabling Row-Level Security on payments tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
        ("core", "0005_add_rls_helper_functions"),  # Depends on RLS helper functions
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Enable RLS on subscription_purchases table
            ALTER TABLE subscription_purchases ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for subscription_purchases
            CREATE POLICY tenant_isolation_policy ON subscription_purchases
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            
            -- Enable RLS on payment_transactions table
            ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for payment_transactions
            CREATE POLICY tenant_isolation_policy ON payment_transactions
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            
            -- Note: subscription_discounts does NOT have RLS as it's global/platform-wide config
            -- All tenants can read discount configuration
            
            -- Create index on tenant_id for performance
            CREATE INDEX IF NOT EXISTS idx_subscription_purchases_tenant 
                ON subscription_purchases (tenant_id);
            
            CREATE INDEX IF NOT EXISTS idx_payment_transactions_tenant 
                ON payment_transactions (tenant_id);
            """,
            reverse_sql="""
            -- Drop indexes
            DROP INDEX IF EXISTS idx_subscription_purchases_tenant;
            DROP INDEX IF EXISTS idx_payment_transactions_tenant;
            
            -- Drop RLS policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON subscription_purchases;
            DROP POLICY IF EXISTS tenant_isolation_policy ON payment_transactions;
            
            -- Disable RLS
            ALTER TABLE subscription_purchases DISABLE ROW LEVEL SECURITY;
            ALTER TABLE payment_transactions DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
