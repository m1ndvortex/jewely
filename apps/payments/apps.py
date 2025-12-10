"""
Payment app configuration.
"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Configuration for the payments app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments & Billing"

    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.payments.signals  # noqa: F401
        except ImportError:
            pass
