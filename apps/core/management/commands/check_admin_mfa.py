"""
Management command to check and report platform admins without MFA enabled.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Check platform administrators for MFA compliance"

    def handle(self, *args, **options):
        """Check all platform admins for MFA status."""
        admins = User.objects.filter(role=User.PLATFORM_ADMIN)
        total_admins = admins.count()
        admins_without_mfa = admins.filter(is_mfa_enabled=False)

        self.stdout.write(f"\nTotal Platform Administrators: {total_admins}")
        self.stdout.write(f"Admins with MFA enabled: {total_admins - admins_without_mfa.count()}")
        self.stdout.write(f"Admins without MFA: {admins_without_mfa.count()}\n")

        if admins_without_mfa.exists():
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  WARNING: The following platform administrators do not have MFA enabled:"
                )
            )
            for admin in admins_without_mfa:
                self.stdout.write(self.style.WARNING(f"  - {admin.username} ({admin.email})"))
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Security Requirement: All platform administrators MUST enable MFA."
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "   Admins without MFA will have restricted access to sensitive operations.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✓ All platform administrators have MFA enabled.\n")
            )
