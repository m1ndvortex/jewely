import smtplib

import pytest
from django.core.mail import EmailMessage

from apps.core.email.backends import ResilientEmailBackend


def test_resilient_backend_routes_to_failover(monkeypatch, settings):
    settings.EMAIL_PRIMARY_BACKEND = "primary.backend"
    settings.EMAIL_FAILOVER_BACKEND = "failover.backend"
    settings.EMAIL_FAILOVER_ENABLED = True
    settings.EMAIL_FAILOVER_SUPPRESS_EXCEPTIONS = True

    class PrimaryConnection:
        def send_messages(self, messages):
            raise smtplib.SMTPException("boom")

    class FailoverConnection:
        def __init__(self):
            self.sent = 0

        def send_messages(self, messages):
            self.sent += len(messages)
            return len(messages)

    failover_conn = FailoverConnection()

    def fake_get_connection(backend_path, fail_silently=False, **kwargs):
        if backend_path == "primary.backend":
            return PrimaryConnection()
        if backend_path == "failover.backend":
            return failover_conn
        raise AssertionError("Unexpected backend path")

    monkeypatch.setattr(
        "apps.core.email.backends.get_connection", fake_get_connection
    )

    backend = ResilientEmailBackend()
    message = EmailMessage(subject="hello", body="world", to=["user@example.com"])

    assert backend.send_messages([message]) == 1
    assert failover_conn.sent == 1


def test_resilient_backend_raises_without_failover(monkeypatch, settings):
    settings.EMAIL_PRIMARY_BACKEND = "primary.backend"
    settings.EMAIL_FAILOVER_BACKEND = "failover.backend"
    settings.EMAIL_FAILOVER_ENABLED = False
    settings.EMAIL_FAILOVER_SUPPRESS_EXCEPTIONS = False

    class PrimaryConnection:
        def send_messages(self, messages):
            raise smtplib.SMTPException("boom")

    def fake_get_connection(backend_path, fail_silently=False, **kwargs):
        if backend_path == "primary.backend":
            return PrimaryConnection()
        raise AssertionError("Unexpected backend path")

    monkeypatch.setattr(
        "apps.core.email.backends.get_connection", fake_get_connection
    )

    backend = ResilientEmailBackend()
    message = EmailMessage(subject="hello", body="world", to=["user@example.com"])

    with pytest.raises(smtplib.SMTPException):
        backend.send_messages([message])
*** End Patch