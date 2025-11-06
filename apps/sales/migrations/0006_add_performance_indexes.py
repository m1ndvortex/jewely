# Generated migration for Task 28.2 - Database Query Optimization
# Adds indexes for sales queries to improve performance
# Per Requirement 26: Performance Optimization and Scaling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_update_customer_fk_to_crm'),
    ]

    operations = [
        # All indexes created with IF NOT EXISTS to avoid conflicts
        migrations.RunSQL(
            sql="""
            -- Sale model indexes
            CREATE INDEX IF NOT EXISTS sale_tenant_status_created_idx ON sales (tenant_id, status, created_at DESC);
            CREATE INDEX IF NOT EXISTS sale_tenant_branch_created_idx ON sales (tenant_id, branch_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS sale_tenant_customer_idx ON sales (tenant_id, customer_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS sale_tenant_employee_idx ON sales (tenant_id, employee_id);
            CREATE INDEX IF NOT EXISTS sale_tenant_terminal_idx ON sales (tenant_id, terminal_id);
            CREATE INDEX IF NOT EXISTS sale_tenant_payment_idx ON sales (tenant_id, payment_method);
            CREATE INDEX IF NOT EXISTS sale_number_idx ON sales (sale_number);
            
            -- Terminal model indexes
            CREATE INDEX IF NOT EXISTS terminal_branch_active_idx ON sales_terminals (branch_id, is_active);
            
            -- SaleItem model indexes
            CREATE INDEX IF NOT EXISTS saleitem_sale_inv_idx ON sale_items (sale_id, inventory_item_id);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS sale_tenant_status_created_idx;
            DROP INDEX IF EXISTS sale_tenant_branch_created_idx;
            DROP INDEX IF EXISTS sale_tenant_customer_idx;
            DROP INDEX IF EXISTS sale_tenant_employee_idx;
            DROP INDEX IF EXISTS sale_tenant_terminal_idx;
            DROP INDEX IF EXISTS sale_tenant_payment_idx;
            DROP INDEX IF EXISTS sale_number_idx;
            DROP INDEX IF EXISTS terminal_branch_active_idx;
            DROP INDEX IF EXISTS saleitem_sale_inv_idx;
            """,
        ),
    ]
