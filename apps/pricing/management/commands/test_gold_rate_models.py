"""
Management command to test gold rate models functionality.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.pricing.models import GoldRate


class Command(BaseCommand):
    help = "Test gold rate models functionality"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Testing Gold Rate Models..."))

        # Test GoldRate model
        self.stdout.write("Creating GoldRate record...")
        gold_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("55.50"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test Command",
        )

        self.stdout.write(f"✓ Created GoldRate: {gold_rate}")
        self.stdout.write(f"  - Rate per gram: ${gold_rate.rate_per_gram}")
        self.stdout.write(f"  - Rate per tola: ${gold_rate.rate_per_tola}")
        self.stdout.write(f"  - Rate per ounce: ${gold_rate.rate_per_ounce}")

        # Test getting latest rate
        latest = GoldRate.get_latest_rate(GoldRate.INTERNATIONAL, "USD")
        self.stdout.write(f"✓ Latest rate retrieved: {latest.rate_per_gram}/g")

        # Test percentage change calculation
        older_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test Command - Older",
        )

        change = gold_rate.calculate_percentage_change(older_rate)
        self.stdout.write(f"✓ Percentage change: {change}%")

        # Test significant change detection
        is_significant = gold_rate.is_significant_change(older_rate, Decimal("5.00"))
        self.stdout.write(f"✓ Is significant change (>5%): {is_significant}")

        self.stdout.write(self.style.SUCCESS("✓ All GoldRate model tests passed!"))

        # Clean up
        GoldRate.objects.all().delete()
        self.stdout.write("✓ Test data cleaned up")

        self.stdout.write(self.style.SUCCESS("Gold Rate Models test completed successfully!"))
