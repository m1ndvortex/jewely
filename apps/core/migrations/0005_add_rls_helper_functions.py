# Generated migration for adding RLS helper functions

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_permissionauditlog"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Create function to get current tenant context
            CREATE OR REPLACE FUNCTION get_current_tenant()
            RETURNS UUID AS $$
            DECLARE
                tenant_uuid TEXT;
            BEGIN
                tenant_uuid := current_setting('app.current_tenant', true);
                IF tenant_uuid IS NULL OR tenant_uuid = '' THEN
                    RETURN NULL;
                END IF;
                RETURN tenant_uuid::UUID;
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN NULL;
            END;
            $$ LANGUAGE plpgsql STABLE;
            
            -- Create function to check if RLS is bypassed
            CREATE OR REPLACE FUNCTION is_rls_bypassed()
            RETURNS BOOLEAN AS $$
            DECLARE
                bypass_setting TEXT;
            BEGIN
                bypass_setting := current_setting('app.bypass_rls', true);
                RETURN bypass_setting = 'true';
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN false;
            END;
            $$ LANGUAGE plpgsql STABLE;
            
            -- Update RLS policies to respect bypass setting
            -- Drop existing policies
            DROP POLICY IF EXISTS tenant_isolation_policy ON branches;
            DROP POLICY IF EXISTS tenant_isolation_policy ON users;
            
            -- Recreate policies with bypass support
            CREATE POLICY tenant_isolation_policy ON branches
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                );
            
            CREATE POLICY tenant_isolation_policy ON users
                USING (
                    is_rls_bypassed() = true
                    OR tenant_id = get_current_tenant()
                    OR tenant_id IS NULL  -- Allow platform admins (no tenant)
                );
            """,
            reverse_sql="""
            -- Drop the helper functions
            DROP FUNCTION IF EXISTS get_current_tenant();
            DROP FUNCTION IF EXISTS is_rls_bypassed();
            
            -- Restore original policies without bypass support
            DROP POLICY IF EXISTS tenant_isolation_policy ON branches;
            DROP POLICY IF EXISTS tenant_isolation_policy ON users;
            
            CREATE POLICY tenant_isolation_policy ON branches
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            
            CREATE POLICY tenant_isolation_policy ON users
                USING (
                    tenant_id = current_setting('app.current_tenant', true)::uuid
                    OR tenant_id IS NULL
                );
            """,
        ),
    ]
