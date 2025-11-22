"""
WSGI config for jewelry shop SaaS platform.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# Initialize OpenTelemetry tracing before Django application
from apps.core.tracing import configure_tracing

configure_tracing()

application = get_wsgi_application()
