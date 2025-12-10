# Generated migration for comprehensive subscription limits
# This migration adds all resource limits needed for maximum flexibility

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add comprehensive resource limits to SubscriptionPlan and TenantSubscription models.
    
    This provides platform administrators with complete flexibility to create
    subscription plans with limits on ANY resource type in the system.
    
    Categories of limits:
    - Core Business: users, branches, inventory, products, contacts, suppliers
    - Sales & POS: pos_terminals, sales_per_month, gift_cards
    - Operations: custom_orders, repair_orders, purchase_orders
    - Marketing: email_campaigns, sms_campaigns, email_notifications, sms_notifications
    - Advanced: api_calls, reports, pricing_rules, journal_entries, loyalty_tiers
    - System: storage, backup_retention_days, concurrent_sessions
    """

    dependencies = [
        ('core', '0030_seed_default_subscription_plans'),
    ]

    operations = [
        # ===== SUBSCRIPTION PLAN - Add new limit fields =====
        
        # Sales & POS Limits
        migrations.AddField(
            model_name='subscriptionplan',
            name='pos_terminals_limit',
            field=models.IntegerField(
                default=1,
                help_text='Maximum number of POS terminals allowed. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='sales_per_month_limit',
            field=models.IntegerField(
                default=500,
                help_text='Maximum number of sales per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='gift_cards_limit',
            field=models.IntegerField(
                default=50,
                help_text='Maximum number of active gift cards. Use -1 for unlimited.'
            ),
        ),
        
        # Business Operations Limits
        migrations.AddField(
            model_name='subscriptionplan',
            name='suppliers_limit',
            field=models.IntegerField(
                default=20,
                help_text='Maximum number of suppliers allowed. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='categories_limit',
            field=models.IntegerField(
                default=50,
                help_text='Maximum number of product categories. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='custom_orders_limit',
            field=models.IntegerField(
                default=50,
                help_text='Maximum number of custom/goldsmith orders per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='repair_orders_limit',
            field=models.IntegerField(
                default=100,
                help_text='Maximum number of repair orders per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='purchase_orders_limit',
            field=models.IntegerField(
                default=50,
                help_text='Maximum number of purchase orders per month. Use -1 for unlimited.'
            ),
        ),
        
        # Marketing & Communication Limits
        migrations.AddField(
            model_name='subscriptionplan',
            name='email_campaigns_limit',
            field=models.IntegerField(
                default=5,
                help_text='Maximum number of email campaigns per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='sms_campaigns_limit',
            field=models.IntegerField(
                default=3,
                help_text='Maximum number of SMS campaigns per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='emails_per_month_limit',
            field=models.IntegerField(
                default=1000,
                help_text='Maximum email notifications per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='sms_per_month_limit',
            field=models.IntegerField(
                default=500,
                help_text='Maximum SMS notifications per month. Use -1 for unlimited.'
            ),
        ),
        
        # Advanced Features Limits
        migrations.AddField(
            model_name='subscriptionplan',
            name='reports_per_month_limit',
            field=models.IntegerField(
                default=50,
                help_text='Maximum custom reports per month. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='pricing_rules_limit',
            field=models.IntegerField(
                default=20,
                help_text='Maximum number of pricing rules. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='journal_entries_limit',
            field=models.IntegerField(
                default=500,
                help_text='Maximum journal entries per month for accounting. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='loyalty_tiers_limit',
            field=models.IntegerField(
                default=5,
                help_text='Maximum number of loyalty tiers. Use -1 for unlimited.'
            ),
        ),
        
        # System Limits
        migrations.AddField(
            model_name='subscriptionplan',
            name='backup_retention_days',
            field=models.IntegerField(
                default=30,
                help_text='Number of days to retain backups. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='concurrent_sessions_limit',
            field=models.IntegerField(
                default=5,
                help_text='Maximum concurrent user sessions. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='documents_limit',
            field=models.IntegerField(
                default=500,
                help_text='Maximum number of document attachments. Use -1 for unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='webhooks_limit',
            field=models.IntegerField(
                default=5,
                help_text='Maximum number of webhooks. Use -1 for unlimited.'
            ),
        ),
        
        # ===== TENANT SUBSCRIPTION - Add override fields for ALL new limits =====
        
        # Sales & POS Override Fields
        migrations.AddField(
            model_name='tenantsubscription',
            name='pos_terminals_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for POS terminals limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='sales_per_month_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for sales per month limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='gift_cards_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for gift cards limit (null = use plan default)'
            ),
        ),
        
        # Business Operations Override Fields
        migrations.AddField(
            model_name='tenantsubscription',
            name='suppliers_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for suppliers limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='categories_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for categories limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='custom_orders_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for custom orders limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='repair_orders_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for repair orders limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='purchase_orders_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for purchase orders limit (null = use plan default)'
            ),
        ),
        
        # Marketing & Communication Override Fields
        migrations.AddField(
            model_name='tenantsubscription',
            name='email_campaigns_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for email campaigns limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='sms_campaigns_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for SMS campaigns limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='emails_per_month_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for emails per month limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='sms_per_month_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for SMS per month limit (null = use plan default)'
            ),
        ),
        
        # Advanced Features Override Fields
        migrations.AddField(
            model_name='tenantsubscription',
            name='reports_per_month_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for reports per month limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='pricing_rules_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for pricing rules limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='journal_entries_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for journal entries limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='loyalty_tiers_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for loyalty tiers limit (null = use plan default)'
            ),
        ),
        
        # System Override Fields
        migrations.AddField(
            model_name='tenantsubscription',
            name='backup_retention_days_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for backup retention days (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='concurrent_sessions_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for concurrent sessions limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='documents_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for documents limit (null = use plan default)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='webhooks_limit_override',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Override for webhooks limit (null = use plan default)'
            ),
        ),
        
        # ===== Monthly Usage Tracking Fields =====
        migrations.AddField(
            model_name='tenantsubscription',
            name='sales_created_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Sales created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='custom_orders_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Custom orders created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='repair_orders_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Repair orders created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='purchase_orders_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Purchase orders created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='email_campaigns_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Email campaigns created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='sms_campaigns_this_month',
            field=models.IntegerField(
                default=0,
                help_text='SMS campaigns created in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='emails_sent_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Emails sent in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='sms_sent_this_month',
            field=models.IntegerField(
                default=0,
                help_text='SMS sent in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='reports_generated_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Reports generated in current billing period'
            ),
        ),
        migrations.AddField(
            model_name='tenantsubscription',
            name='journal_entries_this_month',
            field=models.IntegerField(
                default=0,
                help_text='Journal entries created in current billing period'
            ),
        ),
    ]
