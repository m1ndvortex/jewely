import logging
import smtplib
import socket
from typing import Iterable

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResilientEmailBackend(BaseEmailBackend):
    """Primary SMTP delivery with graceful failover for critical flows."""

    recoverable_exceptions = (
        smtplib.SMTPException,
        socket.timeout,
        ConnectionError,
        OSError,
    )

    def __init__(self, fail_silently: bool = False, **kwargs):
        self.primary_backend_path = getattr(
            settings,
            "EMAIL_PRIMARY_BACKEND",
            "django.core.mail.backends.smtp.EmailBackend",
        )
        self.failover_backend_path = getattr(
            settings,
            "EMAIL_FAILOVER_BACKEND",
            "django.core.mail.backends.console.EmailBackend",
        )
        self.failover_enabled = getattr(settings, "EMAIL_FAILOVER_ENABLED", True)
        self.suppress_exceptions = getattr(
            settings, "EMAIL_FAILOVER_SUPPRESS_EXCEPTIONS", True
        )
        self.primary_backend_kwargs = kwargs.copy()
        self.failover_backend_kwargs = kwargs.copy()
        super().__init__(fail_silently=fail_silently, **kwargs)

    def send_messages(self, email_messages: Iterable) -> int:
        messages = tuple(email_messages)
        if not messages:
            return 0

        try:
            return self._send_with_backend(
                self.primary_backend_path,
                messages,
                self.fail_silently,
                self.primary_backend_kwargs,
            )
        except self.recoverable_exceptions as exc:  # pragma: no cover - network dependent
            logger.error(
                "Primary email backend %s failed: %s",
                self.primary_backend_path,
                exc,
                exc_info=True,
            )
            if not self.failover_enabled:
                if self.fail_silently or self.suppress_exceptions:
                    return 0
                raise
            return self._send_via_failover(messages, exc)

    def _send_with_backend(self, backend_path, email_messages, fail_silently, kwargs):
        connection = get_connection(
            backend_path,
            fail_silently=fail_silently,
            **kwargs,
        )
        return connection.send_messages(email_messages)

    def _send_via_failover(self, email_messages, original_exc):
        try:
            sent = self._send_with_backend(
                self.failover_backend_path,
                email_messages,
                True,
                self.failover_backend_kwargs,
            )
            logger.warning(
                "Rerouted %s email(s) through failover backend %s after %s",
                len(email_messages),
                self.failover_backend_path,
                original_exc,
            )
            return sent
        except Exception as failover_exc:  # pragma: no cover - network dependent
            logger.critical(
                "Failover backend %s also failed: %s",
                self.failover_backend_path,
                failover_exc,
                exc_info=True,
            )
            if self.fail_silently or self.suppress_exceptions:
                return 0
            raise original_exc
