# Generated migration for enabling Row-Level Security on repair tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("repair", "0001_initial"),
    ]

    operations = [
        # Enable RLS on repair tables
        migrations.RunSQL(
            sql="""
            -- Enable RLS on repair_orders table
            ALTER TABLE repair_orders ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for repair_orders
            CREATE POLICY tenant_isolation_policy ON repair_orders
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on custom_orders table
            ALTER TABLE custom_orders ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for custom_orders
            CREATE POLICY tenant_isolation_policy ON custom_orders
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on repair_order_photos table
            -- Note: Photos are isolated through their repair_order relationship
            ALTER TABLE repair_order_photos ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for repair_order_photos
            CREATE POLICY tenant_isolation_policy ON repair_order_photos
                USING (
                    repair_order_id IN (
                        SELECT id FROM repair_orders 
                        WHERE tenant_id = current_setting('app.current_tenant', true)::uuid
                    )
                );
            """,
            reverse_sql="""
            -- Drop RLS policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON repair_orders;
            DROP POLICY IF EXISTS tenant_isolation_policy ON custom_orders;
            DROP POLICY IF EXISTS tenant_isolation_policy ON repair_order_photos;
            
            -- Disable RLS
            ALTER TABLE repair_orders DISABLE ROW LEVEL SECURITY;
            ALTER TABLE custom_orders DISABLE ROW LEVEL SECURITY;
            ALTER TABLE repair_order_photos DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]