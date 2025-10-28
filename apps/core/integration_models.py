"""
External service integration models for API key management and OAuth2.

This module provides:
- API key management for external services (payment gateways, SMS providers, etc.)
- Integration health monitoring
- OAuth2 token management for third-party services

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ExternalService(models.Model):
    """
    External service configuration and API key management.

    Requirement 32.9: Manage API keys for external services including
    payment gateways and SMS providers.
    """

    # Service type choices
    SERVICE_PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    SERVICE_SMS_PROVIDER = "SMS_PROVIDER"
    SERVICE_EMAIL_PROVIDER = "EMAIL_PROVIDER"
    SERVICE_GOLD_RATE_API = "GOLD_RATE_API"
    SERVICE_SHIPPING = "SHIPPING"
    SERVICE_ACCOUNTING = "ACCOUNTING"
    SERVICE_CUSTOM = "CUSTOM"

    SERVICE_TYPE_CHOICES = [
        (SERVICE_PAYMENT_GATEWAY, "Payment Gateway"),
        (SERVICE_SMS_PROVIDER, "SMS Provider"),
        (SERVICE_EMAIL_PROVIDER, "Email Provider"),
        (SERVICE_GOLD_RATE_API, "Gold Rate API"),
        (SERVICE_SHIPPING, "Shipping Service"),
        (SERVICE_ACCOUNTING, "Accounting Integration"),
        (SERVICE_CUSTOM, "Custom Integration"),
    ]

    # Authentication type choices
    AUTH_API_KEY = "API_KEY"
    AUTH_OAUTH2 = "OAUTH2"
    AUTH_BASIC = "BASIC"
    AUTH_BEARER_TOKEN = "BEARER_TOKEN"

    AUTH_TYPE_CHOICES = [
        (AUTH_API_KEY, "API Key"),
        (AUTH_OAUTH2, "OAuth2"),
        (AUTH_BASIC, "Basic Authentication"),
        (AUTH_BEARER_TOKEN, "Bearer Token"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the service",
    )

    # Tenant association
    tenant = models.ForeignKey(
        "Tenant",
        on_delete=models.CASCADE,
        related_name="external_services",
        help_text="Tenant that owns this service integration",
    )

    # Service information
    name = models.CharField(
        max_length=255,
        help_text="Descriptive name for the service",
    )

    service_type = models.CharField(
        max_length=50,
        choices=SERVICE_TYPE_CHOICES,
        help_text="Type of external service",
    )

    provider_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the service provider (e.g., Stripe, Twilio)",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of the service integration",
    )

    # Authentication configuration
    auth_type = models.CharField(
        max_length=50,
        choices=AUTH_TYPE_CHOICES,
        default=AUTH_API_KEY,
        help_text="Authentication method used by this service",
    )

    # API credentials (encrypted in production)
    api_key = models.CharField(
        max_length=500,
        blank=True,
        help_text="API key or client ID (encrypted)",
    )

    api_secret = models.CharField(
        max_length=500,
        blank=True,
        help_text="API secret or client secret (encrypted)",
    )

    # Additional configuration
    base_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Base URL for API endpoints",
    )

    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional configuration parameters",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the service integration is active",
    )

    is_test_mode = models.BooleanField(
        default=False,
        help_text="Whether the service is in test/sandbox mode",
    )

    # Health monitoring
    last_health_check_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last health check",
    )

    health_status = models.CharField(
        max_length=20,
        choices=[
            ("HEALTHY", "Healthy"),
            ("DEGRADED", "Degraded"),
            ("DOWN", "Down"),
            ("UNKNOWN", "Unknown"),
        ],
        default="UNKNOWN",
        help_text="Current health status of the service",
    )

    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Number of consecutive health check failures",
    )

    last_error_message = models.TextField(
        blank=True,
        help_text="Last error message from health check or API call",
    )

    # Usage tracking
    total_requests = models.BigIntegerField(
        default=0,
        help_text="Total number of API requests made",
    )

    failed_requests = models.BigIntegerField(
        default=0,
        help_text="Total number of failed API requests",
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last API request",
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="external_services_created",
        help_text="User who created this service integration",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the service was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the service was last updated",
    )

    class Meta:
        db_table = "external_services"
        ordering = ["-created_at"]
        verbose_name = "External Service"
        verbose_name_plural = "External Services"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "service_type"], name="service_tenant_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="service_tenant_active_idx"),
            models.Index(fields=["health_status"], name="service_health_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"

    def record_request_success(self):
        """Record a successful API request."""
        self.total_requests += 1
        self.last_used_at = timezone.now()
        self.consecutive_failures = 0
        self.health_status = "HEALTHY"
        self.save(
            update_fields=[
                "total_requests",
                "last_used_at",
                "consecutive_failures",
                "health_status",
                "updated_at",
            ]
        )

    def record_request_failure(self, error_message=""):
        """Record a failed API request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_used_at = timezone.now()
        self.consecutive_failures += 1
        self.last_error_message = error_message[:1000]  # Truncate

        # Update health status based on failures
        if self.consecutive_failures >= 5:
            self.health_status = "DOWN"
        elif self.consecutive_failures >= 2:
            self.health_status = "DEGRADED"

        self.save(
            update_fields=[
                "total_requests",
                "failed_requests",
                "last_used_at",
                "consecutive_failures",
                "health_status",
                "last_error_message",
                "updated_at",
            ]
        )

    def get_success_rate(self):
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        successful = self.total_requests - self.failed_requests
        return round((successful / self.total_requests) * 100, 2)

    def is_healthy(self):
        """Check if service is healthy."""
        return self.health_status == "HEALTHY" and self.is_active

    def needs_attention(self):
        """Check if service needs attention."""
        return self.health_status in ["DEGRADED", "DOWN"] or self.consecutive_failures > 0


class OAuth2Token(models.Model):
    """
    OAuth2 token storage for third-party service connections.

    Requirement 32.10: Support OAuth2 for third-party service connections.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the token",
    )

    # Service association
    service = models.OneToOneField(
        ExternalService,
        on_delete=models.CASCADE,
        related_name="oauth2_token",
        help_text="External service this token belongs to",
    )

    # OAuth2 tokens
    access_token = models.CharField(
        max_length=1000,
        help_text="OAuth2 access token (encrypted)",
    )

    refresh_token = models.CharField(
        max_length=1000,
        blank=True,
        help_text="OAuth2 refresh token (encrypted)",
    )

    token_type = models.CharField(
        max_length=50,
        default="Bearer",
        help_text="Token type (usually Bearer)",
    )

    # Token expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the access token expires",
    )

    # Scope
    scope = models.TextField(
        blank=True,
        help_text="OAuth2 scopes granted",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the token was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the token was last updated",
    )

    class Meta:
        db_table = "oauth2_tokens"
        verbose_name = "OAuth2 Token"
        verbose_name_plural = "OAuth2 Tokens"

    def __str__(self):
        return f"OAuth2 Token for {self.service.name}"

    def is_expired(self):
        """Check if access token is expired."""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    def is_expiring_soon(self, minutes=10):
        """Check if token is expiring within specified minutes."""
        if not self.expires_at:
            return False
        threshold = timezone.now() + timedelta(minutes=minutes)
        return self.expires_at <= threshold

    def needs_refresh(self):
        """Check if token needs to be refreshed."""
        return self.is_expired() or self.is_expiring_soon()


class IntegrationHealthCheck(models.Model):
    """
    Track health check results for external service integrations.

    Used for monitoring integration health over time.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the health check",
    )

    # Service association
    service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        related_name="health_checks",
        help_text="External service being checked",
    )

    # Check results
    status = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILURE", "Failure"),
            ("TIMEOUT", "Timeout"),
        ],
        help_text="Result of the health check",
    )

    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds",
    )

    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code (if applicable)",
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if check failed",
    )

    # Metadata
    checked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the health check was performed",
    )

    class Meta:
        db_table = "integration_health_checks"
        ordering = ["-checked_at"]
        verbose_name = "Integration Health Check"
        verbose_name_plural = "Integration Health Checks"
        indexes = [
            models.Index(fields=["service", "-checked_at"], name="health_service_checked_idx"),
            models.Index(fields=["status", "-checked_at"], name="health_status_checked_idx"),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.status} at {self.checked_at}"


class IntegrationLog(models.Model):
    """
    Log all API requests to external services for debugging and auditing.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the log entry",
    )

    # Service association
    service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="External service this log belongs to",
    )

    # Request details
    method = models.CharField(
        max_length=10,
        help_text="HTTP method (GET, POST, etc.)",
    )

    endpoint = models.CharField(
        max_length=500,
        help_text="API endpoint called",
    )

    request_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request headers (sensitive data removed)",
    )

    request_body = models.TextField(
        blank=True,
        help_text="Request body (truncated, sensitive data removed)",
    )

    # Response details
    response_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP response status code",
    )

    response_body = models.TextField(
        blank=True,
        help_text="Response body (truncated)",
    )

    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds",
    )

    # Status
    success = models.BooleanField(
        default=False,
        help_text="Whether the request was successful",
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if request failed",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the request was made",
    )

    class Meta:
        db_table = "integration_logs"
        ordering = ["-created_at"]
        verbose_name = "Integration Log"
        verbose_name_plural = "Integration Logs"
        indexes = [
            models.Index(fields=["service", "-created_at"], name="log_service_created_idx"),
            models.Index(fields=["success", "-created_at"], name="log_success_created_idx"),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.method} {self.endpoint}"
