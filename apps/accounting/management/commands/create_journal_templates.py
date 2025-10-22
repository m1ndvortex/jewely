"""
Management command to create journal entry templates.

This command creates the default journal entry templates for common
business transactions in jewelry shops.
"""

from django.core.management.base import BaseCommand

from apps.accounting.services import AccountingService


class Command(BaseCommand):
    help = "Create default journal entry templates for accounting"

    def handle(self, *args, **options):
        self.stdout.write("Creating journal entry templates...")

        try:
            # Create default chart of accounts templates
            AccountingService._create_default_chart_templates()
            self.stdout.write(self.style.SUCCESS("✓ Default chart of accounts templates created"))

            # Create journal entry templates
            AccountingService._create_journal_templates()
            self.stdout.write(self.style.SUCCESS("✓ Journal entry templates created"))

            self.stdout.write(
                self.style.SUCCESS("Journal entry templates setup completed successfully!")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating journal templates: {str(e)}"))
            raise
