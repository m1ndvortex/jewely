"""
Management command to compress static assets offline (Task 28.3)

This command pre-compresses all static assets for production deployment.
Run this after collectstatic and before deploying to production.

Usage:
    python manage.py compress_assets
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Compress static assets for production deployment"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recompression of all assets",
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting asset compression..."))
        
        # First, collect static files
        self.stdout.write("Collecting static files...")
        call_command("collectstatic", "--noinput", verbosity=1)
        
        # Then compress them
        self.stdout.write("Compressing CSS and JavaScript...")
        try:
            call_command("compress", force=options.get("force", False))
            self.stdout.write(
                self.style.SUCCESS("✓ Asset compression completed successfully!")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Asset compression failed: {str(e)}")
            )
            raise
        
        self.stdout.write(
            self.style.SUCCESS(
                "\nAssets are ready for production deployment."
            )
        )
