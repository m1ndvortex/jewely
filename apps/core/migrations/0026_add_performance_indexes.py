# Generated migration for Task 28.2 - Database Query Optimization
# Adds indexes for common query patterns to improve performance
# Per Requirement 26: Performance Optimization and Scaling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_add_documentation_models'),
    ]

    operations = [
        # All indexes created with IF NOT EXISTS to avoid conflicts
        migrations.RunSQL(
            sql="""
            -- Tenant model indexes
            CREATE INDEX IF NOT EXISTS tenant_status_created_idx ON tenants (status, created_at DESC);
            CREATE INDEX IF NOT EXISTS tenant_slug_idx ON tenants (slug);
            
            -- Branch model indexes
            CREATE INDEX IF NOT EXISTS branch_tenant_active_idx ON branches (tenant_id, is_active);
            CREATE INDEX IF NOT EXISTS branch_tenant_manager_idx ON branches (tenant_id, manager_id);
            
            -- User model indexes
            CREATE INDEX IF NOT EXISTS user_tenant_role_idx ON users (tenant_id, role);
            CREATE INDEX IF NOT EXISTS user_tenant_branch_idx ON users (tenant_id, branch_id);
            CREATE INDEX IF NOT EXISTS user_email_idx ON users (email);
            CREATE INDEX IF NOT EXISTS user_is_active_idx ON users (is_active);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS tenant_status_created_idx;
            DROP INDEX IF EXISTS tenant_slug_idx;
            DROP INDEX IF EXISTS branch_tenant_active_idx;
            DROP INDEX IF EXISTS branch_tenant_manager_idx;
            DROP INDEX IF EXISTS user_tenant_role_idx;
            DROP INDEX IF EXISTS user_tenant_branch_idx;
            DROP INDEX IF EXISTS user_email_idx;
            DROP INDEX IF EXISTS user_is_active_idx;
            """,
        ),
    ]
