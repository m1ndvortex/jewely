"""
Data migration to update existing subscription plans with comprehensive limits.

This migration updates the default plans with the new limit fields added in
migration 0031_add_comprehensive_subscription_limits.

Migration: 0032_update_plans_with_comprehensive_limits
"""

from django.db import migrations


def update_plans_with_new_limits(apps, schema_editor):
    """
    Update existing subscription plans with comprehensive limits.
    
    The new limits cover:
    - Core Business: suppliers, categories, etc.
    - Sales & POS: POS terminals, sales per month, gift cards
    - Operations: custom orders, repair orders, purchase orders
    - Marketing: email campaigns, SMS campaigns, monthly quotas
    - Advanced: pricing rules, journal entries, loyalty tiers
    - System: backup retention, concurrent sessions, documents, webhooks
    
    Uses -1 for unlimited resources in higher tiers.
    """
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    
    # Define comprehensive limits for each plan
    plan_updates = {
        "Free": {
            # Core Business Limits
            "suppliers_limit": 10,
            "categories_limit": 10,
            # Sales & POS Limits
            "pos_terminals_limit": 1,
            "sales_per_month_limit": 50,
            "gift_cards_limit": 0,  # No gift cards in free
            # Operations Limits
            "custom_orders_limit": 5,
            "repair_orders_limit": 5,
            "purchase_orders_limit": 10,
            # Marketing Limits
            "email_campaigns_limit": 0,  # No campaigns in free
            "sms_campaigns_limit": 0,
            "emails_per_month_limit": 50,  # Basic transactional only
            "sms_per_month_limit": 0,
            # Advanced Features
            "reports_per_month_limit": 10,
            "pricing_rules_limit": 0,  # No pricing rules in free
            "journal_entries_limit": 50,
            "loyalty_tiers_limit": 0,  # No loyalty in free
            # System Limits
            "backup_retention_days": 7,
            "concurrent_sessions_limit": 1,
            "documents_limit": 50,
            "webhooks_limit": 0,  # No webhooks in free
        },
        "Starter": {
            # Core Business Limits
            "suppliers_limit": 50,
            "categories_limit": 50,
            # Sales & POS Limits
            "pos_terminals_limit": 2,
            "sales_per_month_limit": 500,
            "gift_cards_limit": 20,
            # Operations Limits
            "custom_orders_limit": 50,
            "repair_orders_limit": 50,
            "purchase_orders_limit": 100,
            # Marketing Limits
            "email_campaigns_limit": 5,
            "sms_campaigns_limit": 0,
            "emails_per_month_limit": 500,
            "sms_per_month_limit": 0,
            # Advanced Features
            "reports_per_month_limit": 50,
            "pricing_rules_limit": 5,
            "journal_entries_limit": 500,
            "loyalty_tiers_limit": 0,
            # System Limits
            "backup_retention_days": 14,
            "concurrent_sessions_limit": 3,
            "documents_limit": 500,
            "webhooks_limit": 2,
        },
        "Professional": {
            # Core Business Limits
            "suppliers_limit": 500,
            "categories_limit": 500,
            # Sales & POS Limits
            "pos_terminals_limit": 10,
            "sales_per_month_limit": 5000,
            "gift_cards_limit": 200,
            # Operations Limits
            "custom_orders_limit": 500,
            "repair_orders_limit": 500,
            "purchase_orders_limit": 1000,
            # Marketing Limits
            "email_campaigns_limit": 50,
            "sms_campaigns_limit": 20,
            "emails_per_month_limit": 5000,
            "sms_per_month_limit": 1000,
            # Advanced Features
            "reports_per_month_limit": 500,
            "pricing_rules_limit": 50,
            "journal_entries_limit": 5000,
            "loyalty_tiers_limit": 5,
            # System Limits
            "backup_retention_days": 30,
            "concurrent_sessions_limit": 10,
            "documents_limit": 5000,
            "webhooks_limit": 10,
        },
        "Enterprise": {
            # Core Business Limits (Unlimited)
            "suppliers_limit": -1,
            "categories_limit": -1,
            # Sales & POS Limits (Unlimited)
            "pos_terminals_limit": -1,
            "sales_per_month_limit": -1,
            "gift_cards_limit": -1,
            # Operations Limits (Unlimited)
            "custom_orders_limit": -1,
            "repair_orders_limit": -1,
            "purchase_orders_limit": -1,
            # Marketing Limits (Unlimited)
            "email_campaigns_limit": -1,
            "sms_campaigns_limit": -1,
            "emails_per_month_limit": -1,
            "sms_per_month_limit": -1,
            # Advanced Features (Unlimited)
            "reports_per_month_limit": -1,
            "pricing_rules_limit": -1,
            "journal_entries_limit": -1,
            "loyalty_tiers_limit": -1,
            # System Limits (Generous)
            "backup_retention_days": 90,
            "concurrent_sessions_limit": -1,
            "documents_limit": -1,
            "webhooks_limit": -1,
        },
    }
    
    for plan_name, limits in plan_updates.items():
        try:
            plan = SubscriptionPlan.objects.get(name=plan_name)
            for field, value in limits.items():
                setattr(plan, field, value)
            plan.save()
            print(f"Updated subscription plan '{plan_name}' with comprehensive limits")
        except SubscriptionPlan.DoesNotExist:
            print(f"Plan '{plan_name}' does not exist. Skipping update.")
    
    print("Successfully updated subscription plans with comprehensive limits.")


def revert_plan_updates(apps, schema_editor):
    """
    Revert the comprehensive limits back to defaults (0).
    
    Note: The schema migration 0031 sets default=0 for all new fields,
    so we just reset to those defaults.
    """
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    
    new_limit_fields = [
        "suppliers_limit",
        "categories_limit",
        "pos_terminals_limit",
        "sales_per_month_limit",
        "gift_cards_limit",
        "custom_orders_limit",
        "repair_orders_limit",
        "purchase_orders_limit",
        "email_campaigns_limit",
        "sms_campaigns_limit",
        "emails_per_month_limit",
        "sms_per_month_limit",
        "reports_per_month_limit",
        "pricing_rules_limit",
        "journal_entries_limit",
        "loyalty_tiers_limit",
        "backup_retention_days",
        "concurrent_sessions_limit",
        "documents_limit",
        "webhooks_limit",
    ]
    
    plan_names = ["Free", "Starter", "Professional", "Enterprise"]
    
    for plan_name in plan_names:
        try:
            plan = SubscriptionPlan.objects.get(name=plan_name)
            for field in new_limit_fields:
                setattr(plan, field, 0)
            plan.save()
            print(f"Reverted limits for plan '{plan_name}'")
        except SubscriptionPlan.DoesNotExist:
            pass


class Migration(migrations.Migration):
    """
    Update existing subscription plans with comprehensive limits.
    """

    dependencies = [
        ("core", "0031_add_comprehensive_subscription_limits"),
    ]

    operations = [
        migrations.RunPython(
            update_plans_with_new_limits,
            revert_plan_updates,
        ),
    ]
