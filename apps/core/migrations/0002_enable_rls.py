# Generated migration for PostgreSQL Row-Level Security (RLS)

from django.db import migrations


class Migration(migrations.Migration):
    """
    Enable PostgreSQL Row-Level Security (RLS) for multi-tenant data isolation.
    
    This migration:
    1. Creates a PostgreSQL function to set tenant context
    2. Enables RLS on tenant-scoped tables
    3. Creates RLS policies using current_setting('app.current_tenant')
    
    Requirements: Requirement 1 - Multi-Tenant Architecture with Data Isolation
    """

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        # Create PostgreSQL function to set tenant context
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
            RETURNS void AS $$
            BEGIN
                -- Set the tenant context in the current session
                -- This value will be used by RLS policies to filter data
                PERFORM set_config('app.current_tenant', tenant_uuid::text, false);
            END;
            $$ LANGUAGE plpgsql SECURITY DEFINER;
            
            -- Add comment to document the function
            COMMENT ON FUNCTION set_tenant_context(UUID) IS 
            'Sets the current tenant context for Row-Level Security policies. '
            'This function must be called at the start of each request to establish tenant isolation.';
            """,
            reverse_sql="""
            DROP FUNCTION IF EXISTS set_tenant_context(UUID);
            """,
        ),
        # Enable Row-Level Security on the tenants table
        migrations.RunSQL(
            sql="""
            -- Enable RLS on tenants table
            ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
            """,
            reverse_sql="""
            -- Disable RLS on tenants table
            ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;
            """,
        ),
        # Force RLS for table owner (important for Django superuser connections)
        migrations.RunSQL(
            sql="""
            -- Force RLS even for table owner (Django typically connects as superuser)
            ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
            """,
            reverse_sql="""
            -- Remove force RLS
            ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;
            """,
        ),
        # Create RLS policy for tenants table - SELECT
        migrations.RunSQL(
            sql="""
            -- Policy: Tenants can only see their own record
            CREATE POLICY tenant_isolation_select_policy ON tenants
                FOR SELECT
                USING (
                    -- Allow access if the tenant_id matches the current session's tenant
                    id::text = current_setting('app.current_tenant', true)
                    OR
                    -- Allow superusers (platform admins) to see all tenants
                    current_setting('app.bypass_rls', true) = 'true'
                );
            
            -- Add comment to document the policy
            COMMENT ON POLICY tenant_isolation_select_policy ON tenants IS
            'Restricts SELECT queries to only return the current tenant''s record. '
            'Platform administrators can bypass this by setting app.bypass_rls=true.';
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_select_policy ON tenants;
            """,
        ),
        # Create RLS policy for tenants table - INSERT
        migrations.RunSQL(
            sql="""
            -- Policy: Only platform admins can insert tenants
            CREATE POLICY tenant_isolation_insert_policy ON tenants
                FOR INSERT
                WITH CHECK (
                    -- Only allow inserts when bypass_rls is enabled (platform admins)
                    current_setting('app.bypass_rls', true) = 'true'
                );
            
            COMMENT ON POLICY tenant_isolation_insert_policy ON tenants IS
            'Only platform administrators can create new tenant records.';
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_insert_policy ON tenants;
            """,
        ),
        # Create RLS policy for tenants table - UPDATE
        migrations.RunSQL(
            sql="""
            -- Policy: Tenants can update their own record, admins can update any
            CREATE POLICY tenant_isolation_update_policy ON tenants
                FOR UPDATE
                USING (
                    id::text = current_setting('app.current_tenant', true)
                    OR
                    current_setting('app.bypass_rls', true) = 'true'
                )
                WITH CHECK (
                    id::text = current_setting('app.current_tenant', true)
                    OR
                    current_setting('app.bypass_rls', true) = 'true'
                );
            
            COMMENT ON POLICY tenant_isolation_update_policy ON tenants IS
            'Tenants can update their own record. Platform administrators can update any tenant.';
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_update_policy ON tenants;
            """,
        ),
        # Create RLS policy for tenants table - DELETE
        migrations.RunSQL(
            sql="""
            -- Policy: Only platform admins can delete tenants
            CREATE POLICY tenant_isolation_delete_policy ON tenants
                FOR DELETE
                USING (
                    current_setting('app.bypass_rls', true) = 'true'
                );
            
            COMMENT ON POLICY tenant_isolation_delete_policy ON tenants IS
            'Only platform administrators can delete tenant records.';
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_delete_policy ON tenants;
            """,
        ),
        # Create helper function to get current tenant ID
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION get_current_tenant()
            RETURNS UUID AS $$
            DECLARE
                tenant_uuid UUID;
            BEGIN
                -- Get the current tenant from session variable
                BEGIN
                    tenant_uuid := current_setting('app.current_tenant', true)::UUID;
                EXCEPTION
                    WHEN OTHERS THEN
                        tenant_uuid := NULL;
                END;
                RETURN tenant_uuid;
            END;
            $$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
            
            COMMENT ON FUNCTION get_current_tenant() IS
            'Returns the current tenant UUID from the session context. '
            'Returns NULL if no tenant context is set.';
            """,
            reverse_sql="""
            DROP FUNCTION IF EXISTS get_current_tenant();
            """,
        ),
        # Create helper function to check if RLS bypass is enabled
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION is_rls_bypassed()
            RETURNS BOOLEAN AS $$
            BEGIN
                RETURN current_setting('app.bypass_rls', true) = 'true';
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN false;
            END;
            $$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
            
            COMMENT ON FUNCTION is_rls_bypassed() IS
            'Returns true if RLS bypass is enabled for the current session (platform admin mode).';
            """,
            reverse_sql="""
            DROP FUNCTION IF EXISTS is_rls_bypassed();
            """,
        ),
    ]
