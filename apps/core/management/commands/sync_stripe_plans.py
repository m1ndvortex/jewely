"""
Management command to sync subscription plans with Stripe.

This command creates or updates Stripe products and prices for all
active subscription plans in the database.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

import stripe

from apps.core.models import SubscriptionPlan

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class Command(BaseCommand):
    help = "Sync subscription plans with Stripe products and prices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating anything",
        )

    def handle(self, *args, **options):  # noqa: C901
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Get all active subscription plans
        plans = SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE)

        if not plans.exists():
            self.stdout.write(self.style.WARNING("No active subscription plans found"))
            return

        self.stdout.write(f"Found {plans.count()} active subscription plans")

        for plan in plans:
            self.stdout.write(f"\nProcessing plan: {plan.name}")

            try:
                # Check if product already exists
                products = stripe.Product.list(limit=100)
                product = next(
                    (p for p in products.data if p.metadata.get("plan_id") == str(plan.id)),
                    None,
                )

                if product:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Product exists: {product.id}"))
                else:
                    if not dry_run:
                        product = stripe.Product.create(
                            name=plan.name,
                            description=plan.description,
                            metadata={"plan_id": str(plan.id)},
                        )
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Created product: {product.id}"))
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  → Would create product for: {plan.name}")
                        )
                        continue

                # Map billing cycle to Stripe interval
                interval_map = {
                    SubscriptionPlan.BILLING_MONTHLY: "month",
                    SubscriptionPlan.BILLING_QUARTERLY: "month",
                    SubscriptionPlan.BILLING_YEARLY: "year",
                }

                interval = interval_map.get(plan.billing_cycle, "month")
                interval_count = (
                    3 if plan.billing_cycle == SubscriptionPlan.BILLING_QUARTERLY else 1
                )

                # Check if price already exists
                prices = stripe.Price.list(product=product.id, limit=100)
                price = next(
                    (
                        p
                        for p in prices.data
                        if p.metadata.get("plan_id") == str(plan.id)
                        and p.unit_amount == int(plan.price * 100)
                        and p.recurring.interval == interval
                        and p.recurring.interval_count == interval_count
                    ),
                    None,
                )

                if price:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Price exists: {price.id}"))
                else:
                    if not dry_run:
                        price = stripe.Price.create(
                            product=product.id,
                            unit_amount=int(plan.price * 100),  # Convert to cents
                            currency="usd",
                            recurring={
                                "interval": interval,
                                "interval_count": interval_count,
                            },
                            metadata={"plan_id": str(plan.id)},
                        )
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Created price: {price.id}"))
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  → Would create price: ${plan.price}/{plan.billing_cycle}"
                            )
                        )

            except stripe.error.StripeError as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Stripe error for {plan.name}: {str(e)}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error for {plan.name}: {str(e)}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN COMPLETE - No changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\nSync complete!"))
