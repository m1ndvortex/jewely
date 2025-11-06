# Generated migration for Task 28.2 - Database Query Optimization
# Adds indexes for inventory queries to improve performance
# Per Requirement 26: Performance Optimization and Scaling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_alter_productcategory_options_and_more'),
    ]

    operations = [
        # All indexes created with IF NOT EXISTS to avoid conflicts
        migrations.RunSQL(
            sql="""
            -- InventoryItem model indexes
            CREATE INDEX IF NOT EXISTS inv_tenant_branch_active_idx ON inventory_items (tenant_id, branch_id, is_active);
            CREATE INDEX IF NOT EXISTS inv_tenant_cat_active_idx ON inventory_items (tenant_id, category_id, is_active);
            CREATE INDEX IF NOT EXISTS inv_tenant_karat_idx ON inventory_items (tenant_id, karat);
            CREATE INDEX IF NOT EXISTS inv_barcode_idx ON inventory_items (barcode);
            CREATE INDEX IF NOT EXISTS inv_serial_idx ON inventory_items (serial_number);
            CREATE INDEX IF NOT EXISTS inv_tenant_qty_idx ON inventory_items (tenant_id, quantity);
            CREATE INDEX IF NOT EXISTS inv_tenant_created_idx ON inventory_items (tenant_id, created_at DESC);
            
            -- InventoryTransfer model indexes
            CREATE INDEX IF NOT EXISTS transfer_tenant_status_idx ON inventory_transfers (tenant_id, status, created_at DESC);
            CREATE INDEX IF NOT EXISTS transfer_from_branch_idx ON inventory_transfers (tenant_id, from_branch_id);
            CREATE INDEX IF NOT EXISTS transfer_to_branch_idx ON inventory_transfers (tenant_id, to_branch_id);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS inv_tenant_branch_active_idx;
            DROP INDEX IF EXISTS inv_tenant_cat_active_idx;
            DROP INDEX IF EXISTS inv_tenant_karat_idx;
            DROP INDEX IF EXISTS inv_barcode_idx;
            DROP INDEX IF EXISTS inv_serial_idx;
            DROP INDEX IF EXISTS inv_tenant_qty_idx;
            DROP INDEX IF EXISTS inv_tenant_created_idx;
            DROP INDEX IF EXISTS transfer_tenant_status_idx;
            DROP INDEX IF EXISTS transfer_from_branch_idx;
            DROP INDEX IF EXISTS transfer_to_branch_idx;
            """,
        ),
    ]
