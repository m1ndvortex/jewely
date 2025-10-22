"""
Sales app configuration.
"""

from django.apps import AppConfig


class SalesConfig(AppConfig):
    """Configuration for the sales app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sales"
    verbose_name = "Sales Management"

    def ready(self):
        """Import signals when app is ready."""
        # Import signals here if needed
        pass
