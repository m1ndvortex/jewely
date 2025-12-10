# Generated manually for subscription system enhancement

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Enhance subscription system with:
    - Multi-currency support (USD/IRR)
    - Additional resource limits (contacts, invoices, products, transactions)
    - Flexible JSON fields for custom limits/features
    - Usage tracking fields
    - New feature flags
    """

    dependencies = [
        ("core", "0028_add_tenant_domain_and_temporary_password"),
    ]

    operations = [
        # ===== SubscriptionPlan New Fields =====
        migrations.AddField(
            model_name="subscriptionplan",
            name="is_free",
            field=models.BooleanField(
                default=False,
                help_text="Mark as free plan (no payment required)",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="price_irr",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Plan price in Iranian Rial (Toman). Use 0 for auto-conversion.",
                max_digits=15,
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="contacts_limit",
            field=models.IntegerField(
                default=100,
                help_text="Maximum number of contacts/customers allowed. Use -1 for unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="invoices_limit",
            field=models.IntegerField(
                default=100,
                help_text="Maximum number of invoices per month. Use -1 for unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="products_limit",
            field=models.IntegerField(
                default=500,
                help_text="Maximum number of products allowed. Use -1 for unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="transactions_limit",
            field=models.IntegerField(
                default=1000,
                help_text="Maximum number of transactions per month. Use -1 for unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="custom_limits",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Custom resource limits as JSON. Example: {'reports_per_day': 10, 'backup_retention_days': 30}",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="custom_features",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Custom feature flags as JSON. Example: {'beta_features': true, 'advanced_analytics': false}",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="enable_export_import",
            field=models.BooleanField(
                default=True,
                help_text="Enable data export/import features",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="enable_email_notifications",
            field=models.BooleanField(
                default=True,
                help_text="Enable email notification features",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="enable_sms_notifications",
            field=models.BooleanField(
                default=False,
                help_text="Enable SMS notification features",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="trial_days",
            field=models.IntegerField(
                default=14,
                help_text="Number of trial days for new subscriptions",
            ),
        ),
        # Update help text for existing limit fields
        migrations.AlterField(
            model_name="subscriptionplan",
            name="user_limit",
            field=models.IntegerField(
                default=5,
                help_text="Maximum number of users allowed. Use -1 for unlimited.",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplan",
            name="branch_limit",
            field=models.IntegerField(
                default=1,
                help_text="Maximum number of branches allowed. Use -1 for unlimited.",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplan",
            name="inventory_limit",
            field=models.IntegerField(
                default=1000,
                help_text="Maximum number of inventory items allowed. Use -1 for unlimited.",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplan",
            name="storage_limit_gb",
            field=models.IntegerField(
                default=10,
                help_text="Maximum storage space in GB for media files. Use -1 for unlimited.",
            ),
        ),
        migrations.AlterField(
            model_name="subscriptionplan",
            name="api_calls_per_month",
            field=models.IntegerField(
                default=10000,
                help_text="Maximum API calls per month. Use -1 for unlimited.",
            ),
        ),
        # Add index for is_free
        migrations.AddIndex(
            model_name="subscriptionplan",
            index=models.Index(fields=["is_free"], name="plan_is_free_idx"),
        ),
        # ===== TenantSubscription New Fields =====
        migrations.AddField(
            model_name="tenantsubscription",
            name="contacts_limit_override",
            field=models.IntegerField(
                blank=True,
                help_text="Override for contacts limit (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="invoices_limit_override",
            field=models.IntegerField(
                blank=True,
                help_text="Override for invoices limit (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="products_limit_override",
            field=models.IntegerField(
                blank=True,
                help_text="Override for products limit (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="transactions_limit_override",
            field=models.IntegerField(
                blank=True,
                help_text="Override for transactions limit (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="enable_export_import_override",
            field=models.BooleanField(
                blank=True,
                help_text="Override for export/import feature (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="enable_email_notifications_override",
            field=models.BooleanField(
                blank=True,
                help_text="Override for email notifications (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="enable_sms_notifications_override",
            field=models.BooleanField(
                blank=True,
                help_text="Override for SMS notifications (null = use plan default)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="custom_limits_override",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Custom limit overrides as JSON",
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="custom_features_override",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Custom feature overrides as JSON",
            ),
        ),
        # Usage tracking fields
        migrations.AddField(
            model_name="tenantsubscription",
            name="api_calls_used_this_month",
            field=models.IntegerField(
                default=0,
                help_text="API calls used in current billing period",
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="invoices_created_this_month",
            field=models.IntegerField(
                default=0,
                help_text="Invoices created in current billing period",
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="transactions_this_month",
            field=models.IntegerField(
                default=0,
                help_text="Transactions in current billing period",
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="storage_used_bytes",
            field=models.BigIntegerField(
                default=0,
                help_text="Storage used in bytes",
            ),
        ),
        migrations.AddField(
            model_name="tenantsubscription",
            name="usage_reset_date",
            field=models.DateTimeField(
                blank=True,
                help_text="Date when monthly usage counters were last reset",
                null=True,
            ),
        ),
    ]
