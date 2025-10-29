from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        """
        Import signal handlers when the app is ready.
        """
        # Import hijack signal handlers to register them
        # Import audit signal handlers to register them
        import apps.core.audit_signals  # noqa: F401
        import apps.core.hijack_signals  # noqa: F401

        # Import job signal handlers for performance tracking
        import apps.core.job_signals  # noqa: F401
