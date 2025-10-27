"""
Comprehensive audit logging models for the jewelry shop SaaS platform.

This module provides models for tracking all administrative actions, user activity,
data modifications, and API requests per Requirement 8.
"""

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    """
    Comprehensive audit log for all system actions.

    Tracks administrative actions, user activity, data modifications,
    and API requests per Requirement 8.
    """

    # Action categories
    CATEGORY_ADMIN = "ADMIN"
    CATEGORY_USER = "USER"
    CATEGORY_DATA = "DATA"
    CATEGORY_API = "API"
    CATEGORY_SECURITY = "SECURITY"
    CATEGORY_SYSTEM = "SYSTEM"

    CATEGORY_CHOICES = [
        (CATEGORY_ADMIN, "Administrative Action"),
        (CATEGORY_USER, "User Activity"),
        (CATEGORY_DATA, "Data Modification"),
        (CATEGORY_API, "API Request"),
        (CATEGORY_SECURITY, "Security Event"),
        (CATEGORY_SYSTEM, "System Event"),
    ]

    # Action types for administrative actions
    ACTION_TENANT_CREATE = "TENANT_CREATE"
    ACTION_TENANT_UPDATE = "TENANT_UPDATE"
    ACTION_TENANT_DELETE = "TENANT_DELETE"
    ACTION_TENANT_SUSPEND = "TENANT_SUSPEND"
    ACTION_TENANT_ACTIVATE = "TENANT_ACTIVATE"
    ACTION_USER_CREATE = "USER_CREATE"
    ACTION_USER_UPDATE = "USER_UPDATE"
    ACTION_USER_DELETE = "USER_DELETE"
    ACTION_SUBSCRIPTION_CREATE = "SUBSCRIPTION_CREATE"
    ACTION_SUBSCRIPTION_UPDATE = "SUBSCRIPTION_UPDATE"
    ACTION_SUBSCRIPTION_CANCEL = "SUBSCRIPTION_CANCEL"
    ACTION_IMPERSONATION_START = "IMPERSONATION_START"
    ACTION_IMPERSONATION_END = "IMPERSONATION_END"

    # Action types for user activity
    ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
    ACTION_LOGIN_FAILED = "LOGIN_FAILED"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_PASSWORD_CHANGE = "PASSWORD_CHANGE"
    ACTION_PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    ACTION_PASSWORD_RESET_COMPLETE = "PASSWORD_RESET_COMPLETE"
    ACTION_MFA_ENABLE = "MFA_ENABLE"
    ACTION_MFA_DISABLE = "MFA_DISABLE"
    ACTION_MFA_VERIFY_SUCCESS = "MFA_VERIFY_SUCCESS"
    ACTION_MFA_VERIFY_FAILED = "MFA_VERIFY_FAILED"

    # Action types for data modifications
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_BULK_CREATE = "BULK_CREATE"
    ACTION_BULK_UPDATE = "BULK_UPDATE"
    ACTION_BULK_DELETE = "BULK_DELETE"

    # Action types for API requests
    ACTION_API_GET = "API_GET"
    ACTION_API_POST = "API_POST"
    ACTION_API_PUT = "API_PUT"
    ACTION_API_PATCH = "API_PATCH"
    ACTION_API_DELETE = "API_DELETE"

    # Action types for security events
    ACTION_SECURITY_BREACH_ATTEMPT = "SECURITY_BREACH_ATTEMPT"
    ACTION_SECURITY_SUSPICIOUS_ACTIVITY = "SECURITY_SUSPICIOUS_ACTIVITY"
    ACTION_SECURITY_RATE_LIMIT_EXCEEDED = "SECURITY_RATE_LIMIT_EXCEEDED"
    ACTION_SECURITY_UNAUTHORIZED_ACCESS = "SECURITY_UNAUTHORIZED_ACCESS"

    ACTION_CHOICES = [
        # Administrative
        (ACTION_TENANT_CREATE, "Tenant Created"),
        (ACTION_TENANT_UPDATE, "Tenant Updated"),
        (ACTION_TENANT_DELETE, "Tenant Deleted"),
        (ACTION_TENANT_SUSPEND, "Tenant Suspended"),
        (ACTION_TENANT_ACTIVATE, "Tenant Activated"),
        (ACTION_USER_CREATE, "User Created"),
        (ACTION_USER_UPDATE, "User Updated"),
        (ACTION_USER_DELETE, "User Deleted"),
        (ACTION_SUBSCRIPTION_CREATE, "Subscription Created"),
        (ACTION_SUBSCRIPTION_UPDATE, "Subscription Updated"),
        (ACTION_SUBSCRIPTION_CANCEL, "Subscription Cancelled"),
        (ACTION_IMPERSONATION_START, "Impersonation Started"),
        (ACTION_IMPERSONATION_END, "Impersonation Ended"),
        # User Activity
        (ACTION_LOGIN_SUCCESS, "Login Successful"),
        (ACTION_LOGIN_FAILED, "Login Failed"),
        (ACTION_LOGOUT, "Logout"),
        (ACTION_PASSWORD_CHANGE, "Password Changed"),
        (ACTION_PASSWORD_RESET_REQUEST, "Password Reset Requested"),
        (ACTION_PASSWORD_RESET_COMPLETE, "Password Reset Completed"),
        (ACTION_MFA_ENABLE, "MFA Enabled"),
        (ACTION_MFA_DISABLE, "MFA Disabled"),
        (ACTION_MFA_VERIFY_SUCCESS, "MFA Verification Successful"),
        (ACTION_MFA_VERIFY_FAILED, "MFA Verification Failed"),
        # Data Modifications
        (ACTION_CREATE, "Record Created"),
        (ACTION_UPDATE, "Record Updated"),
        (ACTION_DELETE, "Record Deleted"),
        (ACTION_BULK_CREATE, "Bulk Records Created"),
        (ACTION_BULK_UPDATE, "Bulk Records Updated"),
        (ACTION_BULK_DELETE, "Bulk Records Deleted"),
        # API Requests
        (ACTION_API_GET, "API GET Request"),
        (ACTION_API_POST, "API POST Request"),
        (ACTION_API_PUT, "API PUT Request"),
        (ACTION_API_PATCH, "API PATCH Request"),
        (ACTION_API_DELETE, "API DELETE Request"),
        # Security Events
        (ACTION_SECURITY_BREACH_ATTEMPT, "Security Breach Attempt"),
        (ACTION_SECURITY_SUSPICIOUS_ACTIVITY, "Suspicious Activity"),
        (ACTION_SECURITY_RATE_LIMIT_EXCEEDED, "Rate Limit Exceeded"),
        (ACTION_SECURITY_UNAUTHORIZED_ACCESS, "Unauthorized Access Attempt"),
    ]

    # Severity levels
    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_ERROR = "ERROR"
    SEVERITY_CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the audit log entry",
    )

    # Tenant association (null for platform-level actions)
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Tenant associated with this action (null for platform actions)",
    )

    # User who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs_performed",
        help_text="User who performed the action",
    )

    # Action details
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        db_index=True,
        help_text="Category of the action",
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text="Specific action performed",
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_INFO,
        db_index=True,
        help_text="Severity level of the action",
    )

    description = models.TextField(
        help_text="Human-readable description of the action",
    )

    # Generic foreign key for the affected object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Type of the affected object",
    )

    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID of the affected object",
    )

    affected_object = GenericForeignKey("content_type", "object_id")

    # Data changes (JSON format)
    old_values = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous values before the change (JSON format)",
    )

    new_values = models.JSONField(
        null=True,
        blank=True,
        help_text="New values after the change (JSON format)",
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IP address of the user",
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string of the browser/client",
    )

    request_method = models.CharField(
        max_length=10,
        blank=True,
        help_text="HTTP request method (GET, POST, PUT, DELETE, etc.)",
    )

    request_path = models.CharField(
        max_length=500,
        blank=True,
        db_index=True,
        help_text="Request path/URL",
    )

    request_params = models.JSONField(
        null=True,
        blank=True,
        help_text="Request parameters (query string and POST data)",
    )

    response_status = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP response status code",
    )

    # Additional metadata
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional metadata (JSON format)",
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the action occurred",
    )

    class Meta:
        db_table = "audit_logs"
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["tenant", "-timestamp"], name="auditlog_tenant_time_idx"),
            models.Index(fields=["user", "-timestamp"], name="auditlog_user_time_idx"),
            models.Index(fields=["category", "-timestamp"], name="auditlog_category_time_idx"),
            models.Index(fields=["action", "-timestamp"], name="auditlog_action_time_idx"),
            models.Index(fields=["severity", "-timestamp"], name="auditlog_severity_time_idx"),
            models.Index(fields=["ip_address", "-timestamp"], name="auditlog_ip_time_idx"),
            models.Index(fields=["request_path", "-timestamp"], name="auditlog_path_time_idx"),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"{self.action} by {user_str} at {self.timestamp}"

    def get_affected_object_display(self):
        """Get a display string for the affected object."""
        if self.affected_object:
            return str(self.affected_object)
        return f"{self.content_type} #{self.object_id}" if self.content_type else "N/A"


class LoginAttempt(models.Model):
    """
    Track login attempts for security monitoring and brute force protection.

    Per Requirement 8.2 - Track user logins, logouts, and failed login attempts.
    """

    # Attempt result
    RESULT_SUCCESS = "SUCCESS"
    RESULT_FAILED_PASSWORD = "FAILED_PASSWORD"
    RESULT_FAILED_USER_NOT_FOUND = "FAILED_USER_NOT_FOUND"
    RESULT_FAILED_ACCOUNT_DISABLED = "FAILED_ACCOUNT_DISABLED"
    RESULT_FAILED_MFA = "FAILED_MFA"
    RESULT_FAILED_RATE_LIMIT = "FAILED_RATE_LIMIT"

    RESULT_CHOICES = [
        (RESULT_SUCCESS, "Successful"),
        (RESULT_FAILED_PASSWORD, "Failed - Invalid Password"),
        (RESULT_FAILED_USER_NOT_FOUND, "Failed - User Not Found"),
        (RESULT_FAILED_ACCOUNT_DISABLED, "Failed - Account Disabled"),
        (RESULT_FAILED_MFA, "Failed - MFA Verification"),
        (RESULT_FAILED_RATE_LIMIT, "Failed - Rate Limit Exceeded"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # User (null if user not found)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_attempts",
    )

    # Username attempted (even if user doesn't exist)
    username = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Username that was attempted",
    )

    # Result
    result = models.CharField(
        max_length=50,
        choices=RESULT_CHOICES,
        db_index=True,
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="IP address of the login attempt",
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string",
    )

    # Geolocation (optional)
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country of the IP address",
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City of the IP address",
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = "login_attempts"
        ordering = ["-timestamp"]
        verbose_name = "Login Attempt"
        verbose_name_plural = "Login Attempts"
        indexes = [
            models.Index(fields=["username", "-timestamp"], name="login_username_time_idx"),
            models.Index(fields=["ip_address", "-timestamp"], name="login_ip_time_idx"),
            models.Index(fields=["result", "-timestamp"], name="login_result_time_idx"),
        ]

    def __str__(self):
        return f"{self.username} - {self.result} from {self.ip_address} at {self.timestamp}"

    def is_successful(self):
        """Check if the login attempt was successful."""
        return self.result == self.RESULT_SUCCESS

    def is_failed(self):
        """Check if the login attempt failed."""
        return not self.is_successful()


class DataChangeLog(models.Model):
    """
    Detailed log of data modifications with before/after values.

    Per Requirement 8.3 - Log all data modifications with before and after values.
    """

    # Change types
    CHANGE_CREATE = "CREATE"
    CHANGE_UPDATE = "UPDATE"
    CHANGE_DELETE = "DELETE"

    CHANGE_CHOICES = [
        (CHANGE_CREATE, "Created"),
        (CHANGE_UPDATE, "Updated"),
        (CHANGE_DELETE, "Deleted"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Tenant association
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_changes",
    )

    # User who made the change
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_changes",
    )

    # Change type
    change_type = models.CharField(
        max_length=10,
        choices=CHANGE_CHOICES,
        db_index=True,
    )

    # Affected object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Type of the modified object",
    )

    object_id = models.CharField(
        max_length=255,
        help_text="ID of the modified object",
    )

    object_repr = models.CharField(
        max_length=500,
        help_text="String representation of the object",
    )

    # Field changes
    field_changes = models.JSONField(
        help_text="Dictionary of field changes: {field_name: {old: value, new: value}}",
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = "data_change_logs"
        ordering = ["-timestamp"]
        verbose_name = "Data Change Log"
        verbose_name_plural = "Data Change Logs"
        indexes = [
            models.Index(
                fields=["content_type", "object_id", "-timestamp"],
                name="data_change_object_idx",
            ),
            models.Index(fields=["tenant", "-timestamp"], name="data_change_tenant_idx"),
            models.Index(fields=["user", "-timestamp"], name="data_change_user_idx"),
            models.Index(fields=["change_type", "-timestamp"], name="data_change_type_idx"),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"{self.change_type} {self.object_repr} by {user_str} at {self.timestamp}"


class APIRequestLog(models.Model):
    """
    Log all API requests with details.

    Per Requirement 8.4 - Log all API requests with user, endpoint, parameters,
    and response status.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Tenant association
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_requests",
    )

    # User who made the request
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_requests",
    )

    # Request details
    method = models.CharField(
        max_length=10,
        db_index=True,
        help_text="HTTP method (GET, POST, PUT, DELETE, etc.)",
    )

    path = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Request path/endpoint",
    )

    query_params = models.JSONField(
        null=True,
        blank=True,
        help_text="Query string parameters",
    )

    request_body = models.JSONField(
        null=True,
        blank=True,
        help_text="Request body (for POST/PUT/PATCH)",
    )

    # Response details
    status_code = models.IntegerField(
        db_index=True,
        help_text="HTTP response status code",
    )

    response_time_ms = models.IntegerField(
        help_text="Response time in milliseconds",
    )

    response_size_bytes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Response size in bytes",
    )

    # Request metadata
    ip_address = models.GenericIPAddressField(
        db_index=True,
    )

    user_agent = models.TextField(
        blank=True,
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = "api_request_logs"
        ordering = ["-timestamp"]
        verbose_name = "API Request Log"
        verbose_name_plural = "API Request Logs"
        indexes = [
            models.Index(fields=["tenant", "-timestamp"], name="api_req_tenant_time_idx"),
            models.Index(fields=["user", "-timestamp"], name="api_req_user_time_idx"),
            models.Index(fields=["method", "-timestamp"], name="api_req_method_time_idx"),
            models.Index(fields=["path", "-timestamp"], name="api_req_path_time_idx"),
            models.Index(fields=["status_code", "-timestamp"], name="api_req_status_time_idx"),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{self.method} {self.path} - {self.status_code} by {user_str}"

    def is_successful(self):
        """Check if the request was successful (2xx status code)."""
        return 200 <= self.status_code < 300

    def is_client_error(self):
        """Check if the request resulted in a client error (4xx status code)."""
        return 400 <= self.status_code < 500

    def is_server_error(self):
        """Check if the request resulted in a server error (5xx status code)."""
        return 500 <= self.status_code < 600
