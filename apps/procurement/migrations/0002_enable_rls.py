"""
Enable Row-Level Security (RLS) for procurement models.

This migration enables RLS policies to ensure tenant data isolation
for all procurement-related tables.
"""

from django.db import migrations


class Migration(migrations.Migration):
    
    dependencies = [
        ('procurement', '0001_initial'),
    ]
    
    operations = [
        # Enable RLS on all procurement tables
        migrations.RunSQL(
            sql="ALTER TABLE procurement_suppliers ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE procurement_suppliers DISABLE ROW LEVEL SECURITY;"
        ),
        migrations.RunSQL(
            sql="ALTER TABLE procurement_purchase_orders ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE procurement_purchase_orders DISABLE ROW LEVEL SECURITY;"
        ),
        migrations.RunSQL(
            sql="ALTER TABLE procurement_purchase_order_items ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE procurement_purchase_order_items DISABLE ROW LEVEL SECURITY;"
        ),
        migrations.RunSQL(
            sql="ALTER TABLE procurement_goods_receipts ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE procurement_goods_receipts DISABLE ROW LEVEL SECURITY;"
        ),
        
        # Create RLS policies for suppliers
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON procurement_suppliers
                USING (tenant_id = current_setting('app.current_tenant')::uuid);
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON procurement_suppliers;"
        ),
        
        # Create RLS policies for purchase orders
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON procurement_purchase_orders
                USING (tenant_id = current_setting('app.current_tenant')::uuid);
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON procurement_purchase_orders;"
        ),
        
        # Create RLS policies for purchase order items (via purchase order)
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON procurement_purchase_order_items
                USING (
                    purchase_order_id IN (
                        SELECT id FROM procurement_purchase_orders 
                        WHERE tenant_id = current_setting('app.current_tenant')::uuid
                    )
                );
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON procurement_purchase_order_items;"
        ),
        
        # Create RLS policies for goods receipts
        migrations.RunSQL(
            sql="""
            CREATE POLICY tenant_isolation_policy ON procurement_goods_receipts
                USING (tenant_id = current_setting('app.current_tenant')::uuid);
            """,
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON procurement_goods_receipts;"
        ),
    ]