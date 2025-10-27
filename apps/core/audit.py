"""
Comprehensive audit logging for the jewelry shop SaaS platform.

This module provides functionality to log all administrative actions, user activity,
data modifications, and API requests for compliance and security auditing purposes
per Requirement 8.
"""

import json
import logging

from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


def log_role_change(actor, target_user, old_role, new_role, request=None):
    """
    Log a role change event.

    Args:
        actor: User who performed the change
        target_user: User whose role was changed
        old_role: Previous role
        new_role: New role
        request: HTTP request object (optional, for IP and user agent)
    """
    from apps.core.models import PermissionAuditLog

    PermissionAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=PermissionAuditLog.ROLE_CHANGED,
        old_value=old_role,
        new_value=new_role,
        description=f"Role changed from {old_role} to {new_role}",
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )


def log_permission_grant(actor, target_user, permission, obj=None, request=None):
    """
    Log a permission grant event.

    Args:
        actor: User who granted the permission
        target_user: User who received the permission
        permission: Permission that was granted
        obj: Object the permission applies to (optional)
        request: HTTP request object (optional)
    """
    from apps.core.models import PermissionAuditLog

    description = f"Granted permission: {permission}"
    if obj:
        description += f" on {obj}"

    PermissionAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=PermissionAuditLog.PERMISSION_GRANTED,
        new_value=json.dumps({"permission": str(permission), "object": str(obj) if obj else None}),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )


def log_permission_revoke(actor, target_user, permission, obj=None, request=None):
    """
    Log a permission revocation event.

    Args:
        actor: User who revoked the permission
        target_user: User who lost the permission
        permission: Permission that was revoked
        obj: Object the permission applied to (optional)
        request: HTTP request object (optional)
    """
    from apps.core.models import PermissionAuditLog

    description = f"Revoked permission: {permission}"
    if obj:
        description += f" on {obj}"

    PermissionAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=PermissionAuditLog.PERMISSION_REVOKED,
        old_value=json.dumps({"permission": str(permission), "object": str(obj) if obj else None}),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )


def log_group_assignment(actor, target_user, group, added=True, request=None):
    """
    Log a group assignment or removal event.

    Args:
        actor: User who performed the action
        target_user: User whose group membership changed
        group: Group that was added or removed
        added: True if group was added, False if removed
        request: HTTP request object (optional)
    """
    from apps.core.models import PermissionAuditLog

    action = PermissionAuditLog.GROUP_ADDED if added else PermissionAuditLog.GROUP_REMOVED
    description = f"{'Added to' if added else 'Removed from'} group: {group.name}"

    PermissionAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=action,
        new_value=group.name if added else "",
        old_value="" if added else group.name,
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )


def log_branch_assignment(actor, target_user, branch, assigned=True, request=None):
    """
    Log a branch assignment or unassignment event.

    Args:
        actor: User who performed the action
        target_user: User whose branch assignment changed
        branch: Branch that was assigned or unassigned
        assigned: True if branch was assigned, False if unassigned
        request: HTTP request object (optional)
    """
    from apps.core.models import PermissionAuditLog

    action = (
        PermissionAuditLog.BRANCH_ASSIGNED if assigned else PermissionAuditLog.BRANCH_UNASSIGNED
    )
    description = f"{'Assigned to' if assigned else 'Unassigned from'} branch: {branch.name if branch else 'None'}"

    PermissionAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=action,
        new_value=str(branch.id) if (assigned and branch) else "",
        old_value="" if assigned else (str(branch.id) if branch else ""),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )


def get_client_ip(request):
    """
    Extract client IP address from request.

    Args:
        request: HTTP request object

    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# ============================================================================
# Administrative Action Logging
# ============================================================================


def log_tenant_action(action, tenant, user=None, old_values=None, new_values=None, request=None):
    """
    Log tenant-related administrative actions.

    Args:
        action: Action type (CREATE, UPDATE, DELETE, SUSPEND, ACTIVATE)
        tenant: Tenant object
        user: User who performed the action
        old_values: Previous values (for updates)
        new_values: New values (for updates/creates)
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    action_map = {
        "CREATE": AuditLog.ACTION_TENANT_CREATE,
        "UPDATE": AuditLog.ACTION_TENANT_UPDATE,
        "DELETE": AuditLog.ACTION_TENANT_DELETE,
        "SUSPEND": AuditLog.ACTION_TENANT_SUSPEND,
        "ACTIVATE": AuditLog.ACTION_TENANT_ACTIVATE,
    }

    description_map = {
        "CREATE": f"Created tenant: {tenant.company_name}",
        "UPDATE": f"Updated tenant: {tenant.company_name}",
        "DELETE": f"Deleted tenant: {tenant.company_name}",
        "SUSPEND": f"Suspended tenant: {tenant.company_name}",
        "ACTIVATE": f"Activated tenant: {tenant.company_name}",
    }

    AuditLog.objects.create(
        tenant=tenant if action != "DELETE" else None,
        user=user,
        category=AuditLog.CATEGORY_ADMIN,
        action=action_map.get(action, AuditLog.ACTION_TENANT_UPDATE),
        severity=(
            AuditLog.SEVERITY_INFO
            if action in ["CREATE", "UPDATE", "ACTIVATE"]
            else AuditLog.SEVERITY_WARNING
        ),
        description=description_map.get(action, f"Tenant action: {action}"),
        content_type=ContentType.objects.get_for_model(tenant),
        object_id=str(tenant.id),
        old_values=old_values,
        new_values=new_values,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_user_action(
    action, target_user, actor=None, old_values=None, new_values=None, request=None
):
    """
    Log user-related administrative actions.

    Args:
        action: Action type (CREATE, UPDATE, DELETE)
        target_user: User object being modified
        actor: User who performed the action
        old_values: Previous values (for updates)
        new_values: New values (for updates/creates)
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    action_map = {
        "CREATE": AuditLog.ACTION_USER_CREATE,
        "UPDATE": AuditLog.ACTION_USER_UPDATE,
        "DELETE": AuditLog.ACTION_USER_DELETE,
    }

    description_map = {
        "CREATE": f"Created user: {target_user.username}",
        "UPDATE": f"Updated user: {target_user.username}",
        "DELETE": f"Deleted user: {target_user.username}",
    }

    AuditLog.objects.create(
        tenant=target_user.tenant if hasattr(target_user, "tenant") else None,
        user=actor,
        category=AuditLog.CATEGORY_ADMIN,
        action=action_map.get(action, AuditLog.ACTION_USER_UPDATE),
        severity=AuditLog.SEVERITY_INFO,
        description=description_map.get(action, f"User action: {action}"),
        content_type=ContentType.objects.get_for_model(target_user),
        object_id=str(target_user.id),
        old_values=old_values,
        new_values=new_values,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_subscription_action(
    action, subscription, user=None, old_values=None, new_values=None, request=None
):
    """
    Log subscription-related administrative actions.

    Args:
        action: Action type (CREATE, UPDATE, CANCEL)
        subscription: Subscription object
        user: User who performed the action
        old_values: Previous values (for updates)
        new_values: New values (for updates/creates)
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    action_map = {
        "CREATE": AuditLog.ACTION_SUBSCRIPTION_CREATE,
        "UPDATE": AuditLog.ACTION_SUBSCRIPTION_UPDATE,
        "CANCEL": AuditLog.ACTION_SUBSCRIPTION_CANCEL,
    }

    description_map = {
        "CREATE": "Created subscription for tenant",
        "UPDATE": "Updated subscription for tenant",
        "CANCEL": "Cancelled subscription for tenant",
    }

    AuditLog.objects.create(
        tenant=subscription.tenant if hasattr(subscription, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_ADMIN,
        action=action_map.get(action, AuditLog.ACTION_SUBSCRIPTION_UPDATE),
        severity=AuditLog.SEVERITY_INFO if action != "CANCEL" else AuditLog.SEVERITY_WARNING,
        description=description_map.get(action, f"Subscription action: {action}"),
        content_type=ContentType.objects.get_for_model(subscription),
        object_id=str(subscription.id),
        old_values=old_values,
        new_values=new_values,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


# ============================================================================
# User Activity Logging
# ============================================================================


def log_login_attempt(username, user=None, success=True, failure_reason=None, request=None):
    """
    Log a login attempt (successful or failed).

    Args:
        username: Username attempted
        user: User object (if found)
        success: Whether the login was successful
        failure_reason: Reason for failure (if applicable)
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog, LoginAttempt

    # Determine result
    if success:
        result = LoginAttempt.RESULT_SUCCESS
        action = AuditLog.ACTION_LOGIN_SUCCESS
        severity = AuditLog.SEVERITY_INFO
        description = f"Successful login: {username}"
    else:
        result_map = {
            "invalid_password": LoginAttempt.RESULT_FAILED_PASSWORD,
            "user_not_found": LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            "account_disabled": LoginAttempt.RESULT_FAILED_ACCOUNT_DISABLED,
            "mfa_failed": LoginAttempt.RESULT_FAILED_MFA,
            "rate_limit": LoginAttempt.RESULT_FAILED_RATE_LIMIT,
        }
        result = result_map.get(failure_reason, LoginAttempt.RESULT_FAILED_PASSWORD)
        action = AuditLog.ACTION_LOGIN_FAILED
        severity = AuditLog.SEVERITY_WARNING
        description = f"Failed login attempt: {username} - {failure_reason or 'unknown reason'}"

    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""

    # Create LoginAttempt record
    LoginAttempt.objects.create(
        user=user,
        username=username,
        result=result,
        ip_address=ip_address or "0.0.0.0",
        user_agent=user_agent,
    )

    # Create AuditLog record
    AuditLog.objects.create(
        tenant=user.tenant if user and hasattr(user, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_USER,
        action=action,
        severity=severity,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        request_method=request.method if request else "",
        request_path=request.path if request else "",
        metadata=(
            {"username": username, "failure_reason": failure_reason}
            if not success
            else {"username": username}
        ),
    )


def log_logout(user, request=None):
    """
    Log a user logout.

    Args:
        user: User who logged out
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    AuditLog.objects.create(
        tenant=user.tenant if hasattr(user, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_USER,
        action=AuditLog.ACTION_LOGOUT,
        severity=AuditLog.SEVERITY_INFO,
        description=f"User logged out: {user.username}",
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_password_change(user, request=None):
    """
    Log a password change.

    Args:
        user: User who changed their password
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    AuditLog.objects.create(
        tenant=user.tenant if hasattr(user, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_USER,
        action=AuditLog.ACTION_PASSWORD_CHANGE,
        severity=AuditLog.SEVERITY_INFO,
        description=f"Password changed: {user.username}",
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_password_reset(user, action="request", request=None):
    """
    Log a password reset request or completion.

    Args:
        user: User requesting/completing password reset
        action: "request" or "complete"
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    if action == "request":
        audit_action = AuditLog.ACTION_PASSWORD_RESET_REQUEST
        description = f"Password reset requested: {user.username}"
    else:
        audit_action = AuditLog.ACTION_PASSWORD_RESET_COMPLETE
        description = f"Password reset completed: {user.username}"

    AuditLog.objects.create(
        tenant=user.tenant if hasattr(user, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_USER,
        action=audit_action,
        severity=AuditLog.SEVERITY_INFO,
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_mfa_action(user, action, success=True, request=None):
    """
    Log MFA-related actions.

    Args:
        user: User performing MFA action
        action: "enable", "disable", or "verify"
        success: Whether the action was successful
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog

    action_map = {
        "enable": AuditLog.ACTION_MFA_ENABLE,
        "disable": AuditLog.ACTION_MFA_DISABLE,
        "verify_success": AuditLog.ACTION_MFA_VERIFY_SUCCESS,
        "verify_failed": AuditLog.ACTION_MFA_VERIFY_FAILED,
    }

    if action == "verify":
        audit_action = action_map["verify_success" if success else "verify_failed"]
        description = f"MFA verification {'successful' if success else 'failed'}: {user.username}"
        severity = AuditLog.SEVERITY_INFO if success else AuditLog.SEVERITY_WARNING
    else:
        audit_action = action_map.get(action, AuditLog.ACTION_MFA_ENABLE)
        description = f"MFA {action}d: {user.username}"
        severity = AuditLog.SEVERITY_INFO

    AuditLog.objects.create(
        tenant=user.tenant if hasattr(user, "tenant") else None,
        user=user,
        category=AuditLog.CATEGORY_USER,
        action=audit_action,
        severity=severity,
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


# ============================================================================
# Data Modification Logging
# ============================================================================


def log_data_change(instance, change_type, user=None, field_changes=None, request=None):
    """
    Log a data modification with before/after values.

    Args:
        instance: Model instance that was modified
        change_type: "CREATE", "UPDATE", or "DELETE"
        user: User who made the change
        field_changes: Dictionary of field changes {field: {old: value, new: value}}
        request: HTTP request object
    """
    from apps.core.audit_models import AuditLog, DataChangeLog

    # Get tenant if instance has one
    tenant = None
    if hasattr(instance, "tenant"):
        tenant = instance.tenant
    elif hasattr(instance, "tenant_id"):
        from apps.core.models import Tenant

        try:
            tenant = Tenant.objects.get(id=instance.tenant_id)
        except Tenant.DoesNotExist:
            pass

    content_type = ContentType.objects.get_for_model(instance)

    # Create DataChangeLog
    DataChangeLog.objects.create(
        tenant=tenant,
        user=user,
        change_type=change_type,
        content_type=content_type,
        object_id=str(instance.pk),
        object_repr=str(instance),
        field_changes=field_changes or {},
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )

    # Create AuditLog
    action_map = {
        "CREATE": AuditLog.ACTION_CREATE,
        "UPDATE": AuditLog.ACTION_UPDATE,
        "DELETE": AuditLog.ACTION_DELETE,
    }

    old_values = {}
    new_values = {}
    if field_changes:
        for field, changes in field_changes.items():
            if "old" in changes:
                old_values[field] = changes["old"]
            if "new" in changes:
                new_values[field] = changes["new"]

    AuditLog.objects.create(
        tenant=tenant,
        user=user,
        category=AuditLog.CATEGORY_DATA,
        action=action_map.get(change_type, AuditLog.ACTION_UPDATE),
        severity=AuditLog.SEVERITY_INFO,
        description=f"{change_type} {content_type.model}: {instance}",
        content_type=content_type,
        object_id=str(instance.pk),
        old_values=old_values if old_values else None,
        new_values=new_values if new_values else None,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


# ============================================================================
# API Request Logging
# ============================================================================


def log_api_request(request, response, response_time_ms):
    """
    Log an API request with details.

    Args:
        request: HTTP request object
        response: HTTP response object
        response_time_ms: Response time in milliseconds
    """
    from apps.core.audit_models import APIRequestLog, AuditLog

    # Get tenant from request
    tenant = getattr(request, "tenant", None)

    # Get user
    user = request.user if request.user.is_authenticated else None

    # Get request body (for POST/PUT/PATCH)
    request_body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            if hasattr(request, "data"):
                request_body = request.data
            elif hasattr(request, "body"):
                import json as json_module

                request_body = json_module.loads(request.body.decode("utf-8"))
        except Exception:
            request_body = None

    # Get query params
    query_params = dict(request.GET) if request.GET else None

    # Get response size
    response_size = None
    if hasattr(response, "content"):
        response_size = len(response.content)

    ip_address = get_client_ip(request)

    # Create APIRequestLog
    APIRequestLog.objects.create(
        tenant=tenant,
        user=user,
        method=request.method,
        path=request.path,
        query_params=query_params,
        request_body=request_body,
        status_code=response.status_code,
        response_time_ms=response_time_ms,
        response_size_bytes=response_size,
        ip_address=ip_address,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    # Create AuditLog for API requests (only for non-GET or errors)
    if request.method != "GET" or response.status_code >= 400:
        action_map = {
            "GET": AuditLog.ACTION_API_GET,
            "POST": AuditLog.ACTION_API_POST,
            "PUT": AuditLog.ACTION_API_PUT,
            "PATCH": AuditLog.ACTION_API_PATCH,
            "DELETE": AuditLog.ACTION_API_DELETE,
        }

        severity = AuditLog.SEVERITY_INFO
        if response.status_code >= 500:
            severity = AuditLog.SEVERITY_ERROR
        elif response.status_code >= 400:
            severity = AuditLog.SEVERITY_WARNING

        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            category=AuditLog.CATEGORY_API,
            action=action_map.get(request.method, AuditLog.ACTION_API_GET),
            severity=severity,
            description=f"{request.method} {request.path} - {response.status_code}",
            ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
            request_params=query_params,
            response_status=response.status_code,
            metadata={
                "response_time_ms": response_time_ms,
                "response_size_bytes": response_size,
            },
        )


# ============================================================================
# Security Event Logging
# ============================================================================


def log_security_event(
    event_type, description, user=None, severity="WARNING", request=None, metadata=None
):
    """
    Log a security event.

    Args:
        event_type: Type of security event (breach_attempt, suspicious_activity, etc.)
        description: Description of the event
        user: User involved (if applicable)
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
        request: HTTP request object
        metadata: Additional metadata
    """
    from apps.core.audit_models import AuditLog

    event_map = {
        "breach_attempt": AuditLog.ACTION_SECURITY_BREACH_ATTEMPT,
        "suspicious_activity": AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        "rate_limit": AuditLog.ACTION_SECURITY_RATE_LIMIT_EXCEEDED,
        "unauthorized_access": AuditLog.ACTION_SECURITY_UNAUTHORIZED_ACCESS,
    }

    severity_map = {
        "INFO": AuditLog.SEVERITY_INFO,
        "WARNING": AuditLog.SEVERITY_WARNING,
        "ERROR": AuditLog.SEVERITY_ERROR,
        "CRITICAL": AuditLog.SEVERITY_CRITICAL,
    }

    AuditLog.objects.create(
        tenant=getattr(request, "tenant", None) if request else None,
        user=user,
        category=AuditLog.CATEGORY_SECURITY,
        action=event_map.get(event_type, AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY),
        severity=severity_map.get(severity, AuditLog.SEVERITY_WARNING),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
        metadata=metadata,
    )


# ============================================================================
# Impersonation Logging (Enhanced)
# ============================================================================


def log_impersonation_start(hijacker, hijacked, request=None):
    """
    Log when a platform admin starts impersonating a tenant user.

    Args:
        hijacker: Platform admin who is impersonating
        hijacked: Tenant user being impersonated
        request: HTTP request object (optional)
    """
    from apps.core.audit_models import AuditLog
    from apps.core.models import PermissionAuditLog

    # Create PermissionAuditLog (existing functionality)
    description = f"Started impersonating user {hijacked.username} (ID: {hijacked.id}, Tenant: {hijacked.tenant.company_name if hijacked.tenant else 'None'})"

    PermissionAuditLog.objects.create(
        actor=hijacker,
        target_user=hijacked,
        action="IMPERSONATION_STARTED",  # Custom action
        new_value=json.dumps(
            {
                "hijacked_user_id": str(hijacked.id),
                "hijacked_username": hijacked.username,
                "hijacked_tenant_id": str(hijacked.tenant.id) if hijacked.tenant else None,
                "hijacked_tenant_name": hijacked.tenant.company_name if hijacked.tenant else None,
            }
        ),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )

    # Create comprehensive AuditLog
    AuditLog.objects.create(
        tenant=hijacked.tenant if hasattr(hijacked, "tenant") else None,
        user=hijacker,
        category=AuditLog.CATEGORY_ADMIN,
        action=AuditLog.ACTION_IMPERSONATION_START,
        severity=AuditLog.SEVERITY_WARNING,
        description=description,
        content_type=ContentType.objects.get_for_model(hijacked),
        object_id=str(hijacked.id),
        new_values={
            "hijacked_user_id": str(hijacked.id),
            "hijacked_username": hijacked.username,
            "hijacked_tenant_id": str(hijacked.tenant.id) if hijacked.tenant else None,
            "hijacked_tenant_name": hijacked.tenant.company_name if hijacked.tenant else None,
        },
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


def log_impersonation_end(hijacker, hijacked, request=None):
    """
    Log when a platform admin stops impersonating a tenant user.

    Args:
        hijacker: Platform admin who was impersonating
        hijacked: Tenant user who was being impersonated
        request: HTTP request object (optional)
    """
    from apps.core.audit_models import AuditLog
    from apps.core.models import PermissionAuditLog

    # Create PermissionAuditLog (existing functionality)
    description = f"Stopped impersonating user {hijacked.username} (ID: {hijacked.id}, Tenant: {hijacked.tenant.company_name if hijacked.tenant else 'None'})"

    PermissionAuditLog.objects.create(
        actor=hijacker,
        target_user=hijacked,
        action="IMPERSONATION_ENDED",  # Custom action
        old_value=json.dumps(
            {
                "hijacked_user_id": str(hijacked.id),
                "hijacked_username": hijacked.username,
                "hijacked_tenant_id": str(hijacked.tenant.id) if hijacked.tenant else None,
                "hijacked_tenant_name": hijacked.tenant.company_name if hijacked.tenant else None,
            }
        ),
        description=description,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )

    # Create comprehensive AuditLog
    AuditLog.objects.create(
        tenant=hijacked.tenant if hasattr(hijacked, "tenant") else None,
        user=hijacker,
        category=AuditLog.CATEGORY_ADMIN,
        action=AuditLog.ACTION_IMPERSONATION_END,
        severity=AuditLog.SEVERITY_INFO,
        description=description,
        content_type=ContentType.objects.get_for_model(hijacked),
        object_id=str(hijacked.id),
        old_values={
            "hijacked_user_id": str(hijacked.id),
            "hijacked_username": hijacked.username,
            "hijacked_tenant_id": str(hijacked.tenant.id) if hijacked.tenant else None,
            "hijacked_tenant_name": hijacked.tenant.company_name if hijacked.tenant else None,
        },
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        request_method=request.method if request else "",
        request_path=request.path if request else "",
    )


# ============================================================================
# Utility Functions
# ============================================================================


def get_model_changes(instance, original_values=None):
    """
    Get field changes for a model instance.

    Args:
        instance: Model instance
        original_values: Dictionary of original field values

    Returns:
        Dictionary of field changes {field: {old: value, new: value}}
    """
    if not original_values:
        return {}

    changes = {}
    for field in instance._meta.fields:
        field_name = field.name
        if field_name in original_values:
            old_value = original_values[field_name]
            new_value = getattr(instance, field_name)

            # Convert to string for comparison
            old_str = str(old_value) if old_value is not None else None
            new_str = str(new_value) if new_value is not None else None

            if old_str != new_str:
                changes[field_name] = {
                    "old": old_value,
                    "new": new_value,
                }

    return changes
