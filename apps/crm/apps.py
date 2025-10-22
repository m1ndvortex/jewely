from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.crm"
    verbose_name = "Customer Relationship Management"

    def ready(self):
        """Import signal handlers when the app is ready."""
        import apps.crm.signals  # noqa: F401
