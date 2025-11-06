# Generated migration for Task 28.2 - Database Query Optimization
# Adds indexes for CRM queries to improve performance
# Per Requirement 26: Performance Optimization and Scaling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_add_customer_accounting_fields'),
    ]

    operations = [
        # Customer model indexes for common queries
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS customer_tenant_idx ON crm_customers (tenant_id);
            CREATE INDEX IF NOT EXISTS customer_tenant_tier_idx ON crm_customers (tenant_id, loyalty_tier_id);
            CREATE INDEX IF NOT EXISTS customer_phone_idx ON crm_customers (phone);
            CREATE INDEX IF NOT EXISTS customer_email_idx ON crm_customers (email);
            CREATE INDEX IF NOT EXISTS customer_number_idx ON crm_customers (customer_number);
            CREATE INDEX IF NOT EXISTS customer_created_idx ON crm_customers (tenant_id, created_at DESC);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS customer_tenant_idx;
            DROP INDEX IF EXISTS customer_tenant_tier_idx;
            DROP INDEX IF EXISTS customer_phone_idx;
            DROP INDEX IF EXISTS customer_email_idx;
            DROP INDEX IF EXISTS customer_number_idx;
            DROP INDEX IF EXISTS customer_created_idx;
            """,
        ),
    ]
