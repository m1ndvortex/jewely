"""
Django management command to encrypt .env file.

Usage:
    docker compose exec web python manage.py encrypt_env
    docker compose exec web python manage.py encrypt_env --env-path /path/to/.env
    docker compose exec web python manage.py encrypt_env --output /path/to/.env.encrypted
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.secrets_management import SecretsManagementError, SecretsManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Encrypt .env file for secure storage"

    def add_arguments(self, parser):
        parser.add_argument(
            "--env-path",
            type=str,
            default=".env",
            help="Path to .env file to encrypt (default: .env)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path for encrypted output file (default: <env-path>.encrypted)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing encrypted file without confirmation",
        )

    def handle(self, *args, **options):
        env_path = options["env_path"]
        output_path = options["output"]
        force = options["force"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Encrypt .env File ==="))
        self.stdout.write("")

        # Check if .env file exists
        if not Path(env_path).exists():
            raise CommandError(f".env file not found: {env_path}")

        # Default output path
        if output_path is None:
            output_path = f"{env_path}.encrypted"

        # Check if output file already exists
        if Path(output_path).exists() and not force:
            self.stdout.write(self.style.WARNING(f"Encrypted file already exists: {output_path}"))
            confirm = input("Overwrite? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Aborted."))
                return

        try:
            # Initialize secrets manager
            self.stdout.write("Initializing secrets manager...")
            manager = SecretsManager()

            # Encrypt .env file
            self.stdout.write(f"Encrypting {env_path}...")
            encrypted_path = manager.encrypt_env_file(env_path, output_path)

            # Success
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✓ Successfully encrypted .env file"))
            self.stdout.write(f"  Input:  {env_path}")
            self.stdout.write(f"  Output: {encrypted_path}")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("IMPORTANT:"))
            self.stdout.write("1. The encrypted file is safe to commit to version control")
            self.stdout.write("2. Keep the SECRETS_MASTER_KEY secure and never commit it")
            self.stdout.write("3. Store SECRETS_MASTER_KEY in environment or Kubernetes secret")
            self.stdout.write("")

        except SecretsManagementError as e:
            raise CommandError(f"Encryption failed: {e}")
        except Exception as e:
            logger.exception("Unexpected error during encryption")
            raise CommandError(f"Unexpected error: {e}")
