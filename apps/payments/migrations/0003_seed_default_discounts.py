# Generated migration for seeding default subscription discounts

from django.db import migrations


def create_default_discounts(apps, schema_editor):
    """Create default subscription discount rules."""
    SubscriptionDiscount = apps.get_model("payments", "SubscriptionDiscount")
    
    default_discounts = [
        {
            "billing_period_months": 1,
            "discount_percentage": 0,
            "description": "Standard monthly billing - no discount",
        },
        {
            "billing_period_months": 3,
            "discount_percentage": 10,
            "description": "Quarterly billing - 10% discount for 3-month commitment",
        },
        {
            "billing_period_months": 6,
            "discount_percentage": 15,
            "description": "Semi-annual billing - 15% discount for 6-month commitment",
        },
        {
            "billing_period_months": 12,
            "discount_percentage": 20,
            "description": "Annual billing - 20% discount for 1-year commitment",
        },
    ]
    
    for discount_data in default_discounts:
        SubscriptionDiscount.objects.get_or_create(
            billing_period_months=discount_data["billing_period_months"],
            defaults={
                "discount_percentage": discount_data["discount_percentage"],
                "description": discount_data["description"],
                "is_active": True,
            }
        )


def remove_default_discounts(apps, schema_editor):
    """Remove default subscription discount rules."""
    SubscriptionDiscount = apps.get_model("payments", "SubscriptionDiscount")
    SubscriptionDiscount.objects.filter(billing_period_months__in=[1, 3, 6, 12]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_enable_rls"),
    ]

    operations = [
        migrations.RunPython(
            create_default_discounts,
            reverse_code=remove_default_discounts,
        ),
    ]
