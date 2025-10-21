"""
Audit logging for permission and role changes.

This module provides functionality to log all permission-related changes
for compliance and security auditing purposes.
"""

import json


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
