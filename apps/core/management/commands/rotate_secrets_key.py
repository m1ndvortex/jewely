"""
Django management command to rotate the master encryption key.

This command should be run quarterly (every 90 days) for security compliance.

Usage:
    docker compose exec web python manage.py rotate_secrets_key
    docker compose exec web python manage.py rotate_secrets_key --reason "Quarterly rotation"
    docker compose exec web python manage.py rotate_secrets_key --no-backup
"""

import hashlib
import logging
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import SecretsKeyRotation
from apps.core.secrets_management import KeyRotationError, SecretsManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rotate the master encryption key (quarterly security requirement)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--env-path",
            type=str,
            default=".env",
            help="Path to .env file (default: .env)",
        )
        parser.add_argument(
            "--reason",
            type=str,
            default="Scheduled quarterly rotation",
            help="Reason for key rotation",
        )
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Skip backup of old encrypted file",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force rotation without confirmation",
        )

    def handle(self, *args, **options):  # noqa: C901
        env_path = options["env_path"]
        reason = options["reason"]
        backup = not options["no_backup"]
        force = options["force"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Rotate Master Encryption Key ==="))
        self.stdout.write("")

        # Check if .env file exists
        if not Path(env_path).exists():
            raise CommandError(f".env file not found: {env_path}")

        # Check last rotation
        last_rotation = SecretsKeyRotation.objects.filter(
            status=SecretsKeyRotation.COMPLETED
        ).first()

        if last_rotation:
            days_since = (timezone.now() - last_rotation.rotation_date).days
            self.stdout.write(f"Last rotation: {last_rotation.rotation_date.strftime('%Y-%m-%d')}")
            self.stdout.write(f"Days since last rotation: {days_since}")

            if days_since < 90 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Last rotation was only {days_since} days ago. "
                        "Quarterly rotation is recommended every 90 days."
                    )
                )
                confirm = input("Continue anyway? (yes/no): ")
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.ERROR("Aborted."))
                    return
        else:
            self.stdout.write(
                self.style.WARNING("No previous rotation found. This is the first rotation.")
            )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("⚠️  WARNING: Key rotation is a critical operation"))
        self.stdout.write("This will:")
        self.stdout.write("1. Generate a new master encryption key")
        self.stdout.write("2. Decrypt .env with the old key")
        self.stdout.write("3. Re-encrypt .env with the new key")
        if backup:
            self.stdout.write("4. Backup the old encrypted file")
        self.stdout.write("")

        if not force:
            confirm = input("Proceed with key rotation? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Aborted."))
                return

        # Create rotation record
        rotation = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.INITIATED,
            rotation_reason=reason,
            old_key_fingerprint="",  # Will be set later
            new_key_fingerprint="",  # Will be set later
        )

        try:
            # Initialize secrets manager
            self.stdout.write("")
            self.stdout.write("Step 1: Initializing secrets manager...")
            manager = SecretsManager()

            # Get old key fingerprint
            old_key_hash = hashlib.sha256(manager.master_key).hexdigest()
            rotation.old_key_fingerprint = old_key_hash
            rotation.save()

            # Generate new key
            self.stdout.write("Step 2: Generating new encryption key...")
            new_key = manager.generate_new_key()
            new_key_bytes = new_key.encode("utf-8")
            new_key_hash = hashlib.sha256(new_key_bytes).hexdigest()
            rotation.new_key_fingerprint = new_key_hash
            rotation.status = SecretsKeyRotation.IN_PROGRESS
            rotation.save()

            # Rotate key
            self.stdout.write("Step 3: Rotating encryption key...")
            encrypted_path, backup_path = manager.rotate_master_key(
                new_key_bytes, env_path, backup=backup
            )

            # Update rotation record
            rotation.files_re_encrypted = [encrypted_path]
            if backup_path:
                rotation.backup_path = backup_path

            # Verify rotation
            self.stdout.write("Step 4: Verifying new encryption...")
            verification_passed = self._verify_rotation(manager, env_path)

            rotation.verification_passed = verification_passed
            rotation.verification_details = {
                "env_file_exists": Path(env_path).exists(),
                "encrypted_file_exists": Path(encrypted_path).exists(),
                "backup_exists": Path(backup_path).exists() if backup_path else False,
            }

            if not verification_passed:
                raise KeyRotationError("Post-rotation verification failed")

            # Mark as completed
            rotation.status = SecretsKeyRotation.COMPLETED
            rotation.completed_at = timezone.now()
            rotation.next_rotation_due = timezone.now() + timedelta(days=90)
            rotation.save()

            # Success
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✓ Key rotation completed successfully"))
            self.stdout.write("")
            self.stdout.write(f"Rotation ID: {rotation.id}")
            self.stdout.write(f"Old key fingerprint: {old_key_hash[:16]}...")
            self.stdout.write(f"New key fingerprint: {new_key_hash[:16]}...")
            if backup_path:
                self.stdout.write(f"Backup: {backup_path}")
            self.stdout.write(
                f"Next rotation due: {rotation.next_rotation_due.strftime('%Y-%m-%d')}"
            )
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("CRITICAL: Update SECRETS_MASTER_KEY"))
            self.stdout.write("You must update the SECRETS_MASTER_KEY environment variable:")
            self.stdout.write("")
            self.stdout.write(f"  export SECRETS_MASTER_KEY='{new_key}'")
            self.stdout.write("")
            self.stdout.write("Or update your Kubernetes secret:")
            self.stdout.write("")
            self.stdout.write("  kubectl create secret generic secrets-master-key \\")
            self.stdout.write(f"    --from-literal=SECRETS_MASTER_KEY='{new_key}' \\")
            self.stdout.write("    --dry-run=client -o yaml | kubectl apply -f -")
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Store the new key securely and never commit it!"))
            self.stdout.write("")

        except KeyRotationError as e:
            rotation.status = SecretsKeyRotation.FAILED
            rotation.error_message = str(e)
            rotation.save()
            raise CommandError(f"Key rotation failed: {e}")
        except Exception as e:
            rotation.status = SecretsKeyRotation.FAILED
            rotation.error_message = str(e)
            rotation.save()
            logger.exception("Unexpected error during key rotation")
            raise CommandError(f"Unexpected error: {e}")

    def _verify_rotation(self, manager, env_path):
        """Verify that the new key works correctly."""
        try:
            # Try to decrypt with new key
            encrypted_path = f"{env_path}.encrypted"
            test_output = f"{env_path}.test"

            manager.decrypt_env_file(encrypted_path, test_output)

            # Verify content matches original
            with open(env_path, "r") as f1, open(test_output, "r") as f2:
                original = f1.read()
                decrypted = f2.read()

            # Clean up test file
            Path(test_output).unlink()

            return original == decrypted

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
