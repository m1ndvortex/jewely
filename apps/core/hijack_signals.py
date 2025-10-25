"""
Signal handlers for django-hijack to log impersonation events.

This module connects to hijack signals to automatically log all
impersonation events for security and compliance purposes.
"""

from django.dispatch import receiver

from hijack import signals

from apps.core.audit import log_impersonation_end, log_impersonation_start


@receiver(signals.hijack_started)
def on_hijack_started(sender, hijacker, hijacked, request, **kwargs):
    """
    Signal handler called when impersonation starts.

    Logs the impersonation event to the audit log.
    """
    log_impersonation_start(hijacker, hijacked, request)


@receiver(signals.hijack_ended)
def on_hijack_ended(sender, hijacker, hijacked, request, **kwargs):
    """
    Signal handler called when impersonation ends.

    Logs the end of impersonation to the audit log.
    """
    log_impersonation_end(hijacker, hijacked, request)
