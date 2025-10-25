"""
App configuration for the backups app.
"""

from django.apps import AppConfig


class BackupsConfig(AppConfig):
    """Configuration for the backups app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backups"
    verbose_name = "Backup & Disaster Recovery"

    def ready(self):
        """
        Import signal handlers when the app is ready.
        """
        # Import signals here to avoid circular imports
        # import apps.backups.signals  # noqa
        pass
