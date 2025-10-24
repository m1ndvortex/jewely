"""
Reporting app configuration.
"""

from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "Reporting & Analytics"

    def ready(self):
        """Import signal handlers when the app is ready."""
        try:
            import apps.reporting.signals  # noqa
        except ImportError:
            pass
