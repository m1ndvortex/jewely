# Migration to enable RLS on tenants table with proper policies

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_add_rls_helper_functions"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- First remove any NO FORCE setting from previous migration
            ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;
            
            -- Enable RLS on tenants table
            ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
            
            -- Policy for SELECT: Allow bypass OR see own tenant
            CREATE POLICY tenant_select_policy ON tenants
                FOR SELECT
                USING (
                    is_rls_bypassed() = true
                    OR id = get_current_tenant()
                );
            
            -- Policy for INSERT: Only with bypass (platform admins only)
            CREATE POLICY tenant_insert_policy ON tenants
                FOR INSERT
                WITH CHECK (is_rls_bypassed() = true);
            
            -- Policy for UPDATE: Allow bypass OR update own tenant
            CREATE POLICY tenant_update_policy ON tenants
                FOR UPDATE
                USING (
                    is_rls_bypassed() = true
                    OR id = get_current_tenant()
                )
                WITH CHECK (
                    is_rls_bypassed() = true
                    OR id = get_current_tenant()
                );
            
            -- Policy for DELETE: Only with bypass (platform admins only)
            CREATE POLICY tenant_delete_policy ON tenants
                FOR DELETE
                USING (is_rls_bypassed() = true);
            """,
            reverse_sql="""
            -- Drop all policies
            DROP POLICY IF EXISTS tenant_select_policy ON tenants;
            DROP POLICY IF EXISTS tenant_insert_policy ON tenants;
            DROP POLICY IF EXISTS tenant_update_policy ON tenants;
            DROP POLICY IF EXISTS tenant_delete_policy ON tenants;
            
            -- Disable RLS
            ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
