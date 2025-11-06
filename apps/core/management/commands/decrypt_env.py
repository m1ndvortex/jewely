"""
Django management command to decrypt .env file.

Usage:
    docker compose exec web python manage.py decrypt_env
    docker compose exec web python manage.py decrypt_env --encrypted-path /path/to/.env.encrypted
    docker compose exec web python manage.py decrypt_env --output /path/to/.env
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.secrets_management import SecretsManagementError, SecretsManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Decrypt encrypted .env file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--encrypted-path",
            type=str,
            default=".env.encrypted",
            help="Path to encrypted .env file (default: .env.encrypted)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path for decrypted output file (default: .env)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing .env file without confirmation",
        )

    def handle(self, *args, **options):
        encrypted_path = options["encrypted_path"]
        output_path = options["output"]
        force = options["force"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Decrypt .env File ==="))
        self.stdout.write("")

        # Check if encrypted file exists
        if not Path(encrypted_path).exists():
            raise CommandError(f"Encrypted file not found: {encrypted_path}")

        # Default output path
        if output_path is None:
            if encrypted_path.endswith(".encrypted"):
                output_path = encrypted_path[:-10]  # Remove .encrypted
            else:
                output_path = ".env"

        # Check if output file already exists
        if Path(output_path).exists() and not force:
            self.stdout.write(self.style.WARNING(f"Output file already exists: {output_path}"))
            confirm = input("Overwrite? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Aborted."))
                return

        try:
            # Initialize secrets manager
            self.stdout.write("Initializing secrets manager...")
            manager = SecretsManager()

            # Decrypt .env file
            self.stdout.write(f"Decrypting {encrypted_path}...")
            decrypted_path = manager.decrypt_env_file(encrypted_path, output_path)

            # Success
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✓ Successfully decrypted .env file"))
            self.stdout.write(f"  Input:  {encrypted_path}")
            self.stdout.write(f"  Output: {decrypted_path}")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("IMPORTANT:"))
            self.stdout.write("1. The decrypted .env file contains sensitive secrets")
            self.stdout.write("2. Never commit the decrypted .env file to version control")
            self.stdout.write("3. Ensure .env is in your .gitignore file")
            self.stdout.write("")

        except SecretsManagementError as e:
            raise CommandError(f"Decryption failed: {e}")
        except Exception as e:
            logger.exception("Unexpected error during decryption")
            raise CommandError(f"Unexpected error: {e}")
