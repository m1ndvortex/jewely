"""
Django management command to generate a new master encryption key.

Usage:
    docker compose exec web python manage.py generate_secrets_key
"""

from django.core.management.base import BaseCommand

from apps.core.secrets_management import SecretsManager


class Command(BaseCommand):
    help = "Generate a new master encryption key for secrets management"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Generate Master Encryption Key ==="))
        self.stdout.write("")

        # Generate new key
        new_key = SecretsManager.generate_new_key()

        self.stdout.write(self.style.SUCCESS("✓ Generated new master encryption key"))
        self.stdout.write("")
        self.stdout.write("Your new master key:")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(new_key))
        self.stdout.write("")
        self.stdout.write("To use this key:")
        self.stdout.write("")
        self.stdout.write("1. Set as environment variable:")
        self.stdout.write(f"   export SECRETS_MASTER_KEY='{new_key}'")
        self.stdout.write("")
        self.stdout.write("2. Or add to Kubernetes secret:")
        self.stdout.write("   kubectl create secret generic secrets-master-key \\")
        self.stdout.write(f"     --from-literal=SECRETS_MASTER_KEY='{new_key}'")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("IMPORTANT:"))
        self.stdout.write("- Store this key securely")
        self.stdout.write("- Never commit it to version control")
        self.stdout.write("- Keep a secure backup")
        self.stdout.write("- This key is required to decrypt your .env file")
        self.stdout.write("")
