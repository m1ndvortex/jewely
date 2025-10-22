# Migration to ensure tenants RLS stays enabled (fixes migration 0003 issue)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_enable_tenants_rls"),
    ]

    operations = [
        # This migration ensures RLS is enabled and stays enabled
        # It counteracts migration 0003 which had IF EXISTS that could run repeatedly
        migrations.RunSQL(
            sql="""
            -- Ensure RLS is enabled with FORCE to prevent it being disabled
            ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
            ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
            
            -- Verify policies exist (they should from migration 0006)
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'tenants' AND policyname = 'tenant_select_policy') THEN
                    RAISE EXCEPTION 'tenant_select_policy does not exist - migration 0006 may have failed';
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
