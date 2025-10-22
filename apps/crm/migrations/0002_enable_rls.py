"""
Enable Row-Level Security (RLS) policies for CRM tables.

This migration implements tenant isolation at the database level
per Requirement 1: Multi-Tenant Architecture with Data Isolation.
"""

from django.db import migrations


class Migration(migrations.Migration):
    
    dependencies = [
        ('crm', '0001_initial'),
        ('core', '0005_add_rls_helper_functions'),  # Ensure RLS helper functions exist
    ]
    
    operations = [
        # Enable RLS on all CRM tables
        migrations.RunSQL(
            sql="ALTER TABLE crm_loyalty_tiers ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE crm_loyalty_tiers DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE crm_customers ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE crm_customers DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE crm_loyalty_transactions ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE crm_loyalty_transactions DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE crm_gift_cards ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE crm_gift_cards DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE crm_customer_communications ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE crm_customer_communications DISABLE ROW LEVEL SECURITY;",
        ),
        
        # Create RLS policies for loyalty tiers
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON crm_loyalty_tiers
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON crm_loyalty_tiers;",
        ),
        
        # Create RLS policies for customers
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON crm_customers
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON crm_customers;",
        ),
        
        # Create RLS policies for loyalty transactions (via customer)
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON crm_loyalty_transactions
                USING (
                    is_rls_bypassed() = true
                    OR customer_id IN (
                        SELECT id FROM crm_customers 
                        WHERE tenant_id = get_current_tenant()
                    )
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON crm_loyalty_transactions;",
        ),
        
        # Create RLS policies for gift cards
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON crm_gift_cards
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON crm_gift_cards;",
        ),
        
        # Create RLS policies for customer communications (via customer)
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON crm_customer_communications
                USING (
                    is_rls_bypassed() = true
                    OR customer_id IN (
                        SELECT id FROM crm_customers 
                        WHERE tenant_id = get_current_tenant()
                    )
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON crm_customer_communications;",
        ),
    ]