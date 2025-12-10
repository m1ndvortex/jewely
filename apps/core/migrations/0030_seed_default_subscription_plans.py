"""
Data migration to seed default subscription plans.

This migration creates the initial set of subscription plans:
- Free: Basic plan for getting started
- Starter: Small businesses
- Professional: Growing businesses
- Enterprise: Large organizations

Migration: 0030_seed_default_subscription_plans
"""

from django.db import migrations


def create_default_plans(apps, schema_editor):
    """
    Create default subscription plans with comprehensive limits and features.
    
    Uses -1 for unlimited resources in higher tiers.
    Multi-currency support with both USD and IRR pricing.
    """
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    
    # Skip if plans already exist
    if SubscriptionPlan.objects.exists():
        print("Subscription plans already exist. Skipping seed.")
        return
    
    default_plans = [
        {
            # Free Plan
            "name": "Free",
            "description": "Perfect for trying out the platform. Limited features but great for getting started.",
            "is_free": True,
            "display_order": 1,
            "trial_days": 0,  # No trial needed for free
            "price": 0,
            "price_irr": 0,
            "billing_cycle": "monthly",
            # Resource Limits (Conservative)
            "user_limit": 1,
            "branch_limit": 1,
            "inventory_limit": 100,
            "contacts_limit": 50,
            "products_limit": 50,
            "invoices_limit": 20,
            "transactions_limit": 50,
            "storage_limit_gb": 1,
            "api_calls_per_month": 1000,
            # Features (Minimal)
            "enable_multi_branch": False,
            "enable_advanced_reporting": False,
            "enable_api_access": False,
            "enable_custom_branding": False,
            "enable_priority_support": False,
            "enable_export_import": False,
            "enable_email_notifications": True,
            "enable_sms_notifications": False,
            "custom_limits": {},
            "custom_features": {},
            "status": "active",
        },
        {
            # Starter Plan
            "name": "Starter",
            "description": "Ideal for small jewelry shops. All essential features to manage your business.",
            "is_free": False,
            "display_order": 2,
            "trial_days": 14,
            "price": 29,
            "price_irr": 1500000,  # ~1.5M Toman
            "billing_cycle": "monthly",
            # Resource Limits (Balanced)
            "user_limit": 3,
            "branch_limit": 1,
            "inventory_limit": 1000,
            "contacts_limit": 500,
            "products_limit": 500,
            "invoices_limit": 100,
            "transactions_limit": 500,
            "storage_limit_gb": 5,
            "api_calls_per_month": 10000,
            # Features (Basic)
            "enable_multi_branch": False,
            "enable_advanced_reporting": True,
            "enable_api_access": False,
            "enable_custom_branding": False,
            "enable_priority_support": False,
            "enable_export_import": True,
            "enable_email_notifications": True,
            "enable_sms_notifications": False,
            "custom_limits": {},
            "custom_features": {},
            "status": "active",
        },
        {
            # Professional Plan
            "name": "Professional",
            "description": "For growing businesses. Multi-branch support, advanced features, and priority support.",
            "is_free": False,
            "display_order": 3,
            "trial_days": 14,
            "price": 79,
            "price_irr": 4000000,  # ~4M Toman
            "billing_cycle": "monthly",
            # Resource Limits (Generous)
            "user_limit": 10,
            "branch_limit": 5,
            "inventory_limit": 10000,
            "contacts_limit": 5000,
            "products_limit": 5000,
            "invoices_limit": 500,
            "transactions_limit": 5000,
            "storage_limit_gb": 25,
            "api_calls_per_month": 100000,
            # Features (Advanced)
            "enable_multi_branch": True,
            "enable_advanced_reporting": True,
            "enable_api_access": True,
            "enable_custom_branding": True,
            "enable_priority_support": True,
            "enable_export_import": True,
            "enable_email_notifications": True,
            "enable_sms_notifications": True,
            "custom_limits": {
                "reports_per_day": 50,
                "backup_retention_days": 30,
            },
            "custom_features": {
                "scheduled_reports": True,
                "multi_currency": True,
            },
            "status": "active",
        },
        {
            # Enterprise Plan
            "name": "Enterprise",
            "description": "Unlimited resources, dedicated support, custom integrations, and SLA guarantees.",
            "is_free": False,
            "display_order": 4,
            "trial_days": 30,
            "price": 199,
            "price_irr": 10000000,  # ~10M Toman
            "billing_cycle": "monthly",
            # Resource Limits (Unlimited)
            "user_limit": -1,  # Unlimited
            "branch_limit": -1,  # Unlimited
            "inventory_limit": -1,  # Unlimited
            "contacts_limit": -1,  # Unlimited
            "products_limit": -1,  # Unlimited
            "invoices_limit": -1,  # Unlimited
            "transactions_limit": -1,  # Unlimited
            "storage_limit_gb": 100,
            "api_calls_per_month": -1,  # Unlimited
            # Features (All)
            "enable_multi_branch": True,
            "enable_advanced_reporting": True,
            "enable_api_access": True,
            "enable_custom_branding": True,
            "enable_priority_support": True,
            "enable_export_import": True,
            "enable_email_notifications": True,
            "enable_sms_notifications": True,
            "custom_limits": {
                "reports_per_day": -1,
                "backup_retention_days": 90,
                "concurrent_api_connections": 100,
            },
            "custom_features": {
                "scheduled_reports": True,
                "multi_currency": True,
                "dedicated_support": True,
                "custom_integrations": True,
                "sla_guarantee": True,
                "on_premise_option": True,
            },
            "status": "active",
        },
    ]
    
    for plan_data in default_plans:
        SubscriptionPlan.objects.create(**plan_data)
        print(f"Created subscription plan: {plan_data['name']}")
    
    print(f"Successfully created {len(default_plans)} default subscription plans.")


def remove_default_plans(apps, schema_editor):
    """
    Remove the default subscription plans.
    Only removes plans that were created by this migration (based on name).
    """
    SubscriptionPlan = apps.get_model("core", "SubscriptionPlan")
    
    default_plan_names = ["Free", "Starter", "Professional", "Enterprise"]
    
    # Only delete plans that don't have any subscriptions
    for plan_name in default_plan_names:
        try:
            plan = SubscriptionPlan.objects.get(name=plan_name)
            if plan.subscriptions.count() == 0:
                plan.delete()
                print(f"Deleted subscription plan: {plan_name}")
            else:
                print(f"Skipped deletion of {plan_name} - has active subscriptions")
        except SubscriptionPlan.DoesNotExist:
            pass


class Migration(migrations.Migration):
    """
    Seed default subscription plans for the jewelry shop SaaS platform.
    """

    dependencies = [
        ("core", "0029_enhance_subscription_system"),
    ]

    operations = [
        migrations.RunPython(
            create_default_plans,
            remove_default_plans,
        ),
    ]
