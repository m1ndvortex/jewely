# Generated migration for enabling Row-Level Security on sales tables

from django.db import migrations


class Migration(migrations.Migration):
    """
    Enable PostgreSQL Row-Level Security (RLS) on sales tables.
    
    Implements Requirement 1: Multi-Tenant Architecture with Data Isolation
    - Enforces tenant isolation at the database level
    - Prevents cross-tenant data access through RLS policies
    - Uses current_setting('app.current_tenant') for tenant context
    
    Tables with RLS:
    - sales_customers: Customer data is tenant-scoped
    - sales: Sales transactions are tenant-scoped
    - sale_items: Sale items inherit tenant scope from sales
    - sales_terminals: Terminals are tenant-scoped via branch relationship
    """

    dependencies = [
        ("sales", "0001_initial"),
        ("core", "0002_enable_rls"),  # Ensure set_tenant_context function exists
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Enable RLS on sales_customers table
            ALTER TABLE sales_customers ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for customers
            CREATE POLICY tenant_isolation_policy ON sales_customers
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on sales table
            ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for sales
            CREATE POLICY tenant_isolation_policy ON sales
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on sale_items table
            -- Sale items are tenant-scoped through their parent sale
            ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for sale_items (via sale relationship)
            CREATE POLICY tenant_isolation_policy ON sale_items
                USING (
                    sale_id IN (
                        SELECT id FROM sales 
                        WHERE tenant_id = current_setting('app.current_tenant', true)::uuid
                    )
                );
            
            -- Enable RLS on sales_terminals table
            -- Terminals are tenant-scoped through their branch relationship
            ALTER TABLE sales_terminals ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for terminals (via branch relationship)
            CREATE POLICY tenant_isolation_policy ON sales_terminals
                USING (
                    branch_id IN (
                        SELECT id FROM branches 
                        WHERE tenant_id = current_setting('app.current_tenant', true)::uuid
                    )
                );
            
            -- Create indexes to optimize RLS policy checks
            CREATE INDEX IF NOT EXISTS sale_items_sale_tenant_idx 
                ON sale_items(sale_id);
            
            CREATE INDEX IF NOT EXISTS terminals_branch_tenant_idx 
                ON sales_terminals(branch_id);
            """,
            reverse_sql="""
            -- Drop indexes
            DROP INDEX IF EXISTS sale_items_sale_tenant_idx;
            DROP INDEX IF EXISTS terminals_branch_tenant_idx;
            
            -- Drop RLS policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON sales_customers;
            DROP POLICY IF EXISTS tenant_isolation_policy ON sales;
            DROP POLICY IF EXISTS tenant_isolation_policy ON sale_items;
            DROP POLICY IF EXISTS tenant_isolation_policy ON sales_terminals;
            
            -- Disable RLS
            ALTER TABLE sales_customers DISABLE ROW LEVEL SECURITY;
            ALTER TABLE sales DISABLE ROW LEVEL SECURITY;
            ALTER TABLE sale_items DISABLE ROW LEVEL SECURITY;
            ALTER TABLE sales_terminals DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
