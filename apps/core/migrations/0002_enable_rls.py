# Generated migration for enabling Row-Level Security

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        # Enable RLS on tenant-scoped tables
        # Note: Tenants table does NOT have RLS as it's not tenant-scoped data
        migrations.RunSQL(
            sql="""
            -- Create function to set tenant context
            CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
            RETURNS void AS $$
            BEGIN
                PERFORM set_config('app.current_tenant', tenant_uuid::text, false);
            END;
            $$ LANGUAGE plpgsql;
            
            -- Enable RLS on branches table
            ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for branches
            CREATE POLICY tenant_isolation_policy ON branches
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            -- Enable RLS on users table
            ALTER TABLE users ENABLE ROW LEVEL SECURITY;
            
            -- Create RLS policy for users
            CREATE POLICY tenant_isolation_policy ON users
                USING (
                    tenant_id = current_setting('app.current_tenant', true)::uuid
                    OR tenant_id IS NULL  -- Allow platform admins (no tenant)
                );
            """,
            reverse_sql="""
            -- Drop RLS policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON branches;
            DROP POLICY IF EXISTS tenant_isolation_policy ON users;
            
            -- Disable RLS
            ALTER TABLE branches DISABLE ROW LEVEL SECURITY;
            ALTER TABLE users DISABLE ROW LEVEL SECURITY;
            
            -- Drop function
            DROP FUNCTION IF EXISTS set_tenant_context(UUID);
            """,
        ),
    ]
