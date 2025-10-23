"""
Management command to manually fetch gold rates.

Usage:
    python manage.py fetch_gold_rates
    python manage.py fetch_gold_rates --market LONDON
"""

from django.core.management.base import BaseCommand

from apps.pricing.models import GoldRate
from apps.pricing.tasks import fetch_gold_rates


class Command(BaseCommand):
    """Management command to fetch gold rates from external APIs."""

    help = "Fetch current gold rates from external APIs and store them"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--market",
            type=str,
            default=GoldRate.INTERNATIONAL,
            choices=[choice[0] for choice in GoldRate.MARKET_CHOICES],
            help="Market to fetch rates for (default: INTERNATIONAL)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        market = options["market"]

        self.stdout.write(self.style.WARNING(f"Fetching gold rates for market: {market}..."))

        try:
            # Call the Celery task directly (synchronously for management command)
            result = fetch_gold_rates(market=market)

            if result:
                self.stdout.write(self.style.SUCCESS(f"✓ {result}"))

                # Display the latest rate
                latest_rate = GoldRate.get_latest_rate(market=market)
                if latest_rate:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"\nLatest Rate Information:"
                            f"\n  Rate per gram: {latest_rate.rate_per_gram}"
                            f"\n  Rate per tola: {latest_rate.rate_per_tola}"
                            f"\n  Rate per ounce: {latest_rate.rate_per_ounce}"
                            f"\n  Currency: {latest_rate.currency}"
                            f"\n  Source: {latest_rate.source}"
                            f"\n  Timestamp: {latest_rate.timestamp}"
                        )
                    )
            else:
                self.stdout.write(self.style.ERROR("✗ Failed to fetch gold rates"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            raise
