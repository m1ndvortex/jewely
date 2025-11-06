"""
Sentry Configuration and Data Scrubbing

This module provides Sentry initialization with comprehensive data scrubbing
to ensure sensitive information is never sent to Sentry.

Requirements:
- 24.8: Integrate Sentry for error tracking with automatic error grouping
- 25.10: Mask sensitive data in logs and error reports
"""

import re
from typing import Any, Dict, Optional

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# Sensitive field patterns to scrub
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth",
    "authorization",
    "cookie",
    "csrf",
    "session",
    "private_key",
    "public_key",
    "encryption_key",
    "credit_card",
    "card_number",
    "cvv",
    "ssn",
    "social_security",
}

# Regex patterns for sensitive data
CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")


def scrub_sensitive_data(data: Any) -> Any:
    """
    Recursively scrub sensitive data from dictionaries, lists, and strings.

    Args:
        data: Data to scrub (dict, list, str, or other)

    Returns:
        Scrubbed data with sensitive information masked
    """
    if isinstance(data, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else scrub_sensitive_data(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [scrub_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        return _scrub_string(data)
    else:
        return data


def _is_sensitive_key(key: str) -> bool:
    """
    Check if a key name indicates sensitive data.

    Args:
        key: Dictionary key to check

    Returns:
        True if key is sensitive, False otherwise
    """
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def _scrub_string(text: str) -> str:
    """
    Scrub sensitive patterns from strings.

    Args:
        text: String to scrub

    Returns:
        String with sensitive patterns masked
    """
    # Mask credit card numbers
    text = CREDIT_CARD_PATTERN.sub("XXXX-XXXX-XXXX-XXXX", text)

    # Partially mask email addresses (keep first 2 chars and domain)
    text = EMAIL_PATTERN.sub(lambda m: _mask_email(m.group(0)), text)

    # Partially mask phone numbers (keep last 4 digits)
    text = PHONE_PATTERN.sub(lambda m: f"XXX-XXX-{m.group(0)[-4:]}", text)

    return text


def _mask_email(email: str) -> str:
    """
    Partially mask an email address.

    Args:
        email: Email address to mask

    Returns:
        Masked email (e.g., jo***@example.com)
    """
    try:
        local, domain = email.split("@")
        if len(local) <= 1:
            masked_local = local[0] + "*"
        elif len(local) == 2:
            masked_local = local + "***"
        else:
            masked_local = local[:2] + "***"
        return f"{masked_local}@{domain}"
    except (ValueError, IndexError):
        return "REDACTED@EMAIL"


def before_send(  # noqa: C901
    event: Dict[str, Any], hint: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Sentry before_send hook to scrub sensitive data from events.

    This function is called before every event is sent to Sentry,
    allowing us to modify or drop events.

    Args:
        event: Sentry event dictionary
        hint: Additional context about the event

    Returns:
        Modified event or None to drop the event
    """
    # Scrub request data
    if "request" in event:
        request = event["request"]

        # Scrub headers
        if "headers" in request:
            request["headers"] = scrub_sensitive_data(request["headers"])

        # Scrub cookies
        if "cookies" in request:
            request["cookies"] = {k: "[REDACTED]" for k in request["cookies"]}

        # Scrub query string
        if "query_string" in request:
            request["query_string"] = scrub_sensitive_data(request["query_string"])

        # Scrub POST data
        if "data" in request:
            request["data"] = scrub_sensitive_data(request["data"])

    # Scrub extra context
    if "extra" in event:
        event["extra"] = scrub_sensitive_data(event["extra"])

    # Scrub user data (keep id and username, scrub email and IP)
    if "user" in event:
        user = event["user"]
        if "email" in user:
            user["email"] = _mask_email(user["email"])
        if "ip_address" in user:
            user["ip_address"] = "XXX.XXX.XXX.XXX"

    # Scrub exception values
    if "exception" in event and "values" in event["exception"]:
        for exception in event["exception"]["values"]:
            if "value" in exception:
                exception["value"] = _scrub_string(exception["value"])

    # Scrub breadcrumbs
    if "breadcrumbs" in event and "values" in event["breadcrumbs"]:
        for breadcrumb in event["breadcrumbs"]["values"]:
            if "data" in breadcrumb:
                breadcrumb["data"] = scrub_sensitive_data(breadcrumb["data"])
            if "message" in breadcrumb:
                breadcrumb["message"] = _scrub_string(breadcrumb["message"])

    return event


def initialize_sentry(
    dsn: Optional[str],
    environment: str = "development",
    traces_sample_rate: float = 0.1,
    release: Optional[str] = None,
) -> None:
    """
    Initialize Sentry SDK with Django, Celery, and Redis integrations.

    Args:
        dsn: Sentry DSN (Data Source Name). If None, Sentry is not initialized.
        environment: Environment name (development, staging, production)
        traces_sample_rate: Percentage of transactions to trace (0.0 to 1.0)
        release: Release version string
    """
    if not dsn:
        # Sentry is disabled if no DSN is provided
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        # Integrations
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
                signals_spans=True,
                cache_spans=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                exclude_beat_tasks=None,
            ),
            RedisIntegration(),
        ],
        # Data scrubbing
        before_send=before_send,
        # Send default PII (we'll scrub it in before_send)
        send_default_pii=False,
        # Attach stack traces to messages
        attach_stacktrace=True,
        # Maximum breadcrumbs
        max_breadcrumbs=50,
        # Debug mode (only for development)
        debug=environment == "development",
        # Request bodies
        request_bodies="medium",  # 'never', 'small', 'medium', 'always'
        # Performance monitoring
        enable_tracing=True,
        # Profiles sample rate (for profiling)
        profiles_sample_rate=0.1 if environment == "production" else 0.0,
    )
