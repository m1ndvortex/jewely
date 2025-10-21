# Generated migration for enabling Row-Level Security on inventory tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        # Enable RLS on inventory tables
        migrations.RunSQL(
            sql="""
            -- Enable RLS on inventory_categories table
            ALTER TABLE inventory_categories ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for inventory_categories
            CREATE POLICY tenant_isolation_policy ON inventory_categories
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on inventory_items table
            ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for inventory_items
            CREATE POLICY tenant_isolation_policy ON inventory_items
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            """,
            reverse_sql="""
            -- Drop RLS policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON inventory_categories;
            DROP POLICY IF EXISTS tenant_isolation_policy ON inventory_items;
            
            -- Disable RLS
            ALTER TABLE inventory_categories DISABLE ROW LEVEL SECURITY;
            ALTER TABLE inventory_items DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
