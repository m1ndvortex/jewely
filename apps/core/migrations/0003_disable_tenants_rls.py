# Migration to ensure tenants table does not have RLS enabled

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_enable_rls"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Ensure tenants table does NOT have RLS
            -- Tenants table is not tenant-scoped data - it's the master list of all tenants
            -- Platform admins need to see all tenants, not filtered by tenant context
            ALTER TABLE IF EXISTS tenants NO FORCE ROW LEVEL SECURITY;
            ALTER TABLE IF EXISTS tenants DISABLE ROW LEVEL SECURITY;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
