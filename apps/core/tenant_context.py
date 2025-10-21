"""
Tenant context management utilities for Row-Level Security (RLS).

This module provides utilities to set and manage the PostgreSQL session
variables that control RLS policies for multi-tenant data isolation.
"""

import logging
from contextlib import contextmanager
from typing import Optional
from uuid import UUID

from django.db import connection

logger = logging.getLogger(__name__)


def set_tenant_context(tenant_id: Optional[UUID]) -> None:
    """
    Set the tenant context for the current database session.

    This function sets the PostgreSQL session variable 'app.current_tenant'
    which is used by Row-Level Security policies to filter data.

    Args:
        tenant_id: UUID of the tenant to set as context. If None, clears the context.

    Example:
        >>> from apps.core.tenant_context import set_tenant_context
        >>> tenant_id = UUID('123e4567-e89b-12d3-a456-426614174000')
        >>> set_tenant_context(tenant_id)

    Requirements: Requirement 1 - Multi-Tenant Architecture with Data Isolation
    """
    with connection.cursor() as cursor:
        if tenant_id is None:
            # Clear the tenant context
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            logger.debug("Cleared tenant context")
        else:
            # Set the tenant context using the PostgreSQL function
            cursor.execute("SELECT set_tenant_context(%s);", [str(tenant_id)])
            logger.debug(f"Set tenant context to: {tenant_id}")


def get_current_tenant() -> Optional[UUID]:
    """
    Get the current tenant ID from the database session.

    Returns:
        UUID of the current tenant, or None if no tenant context is set.

    Example:
        >>> from apps.core.tenant_context import get_current_tenant
        >>> tenant_id = get_current_tenant()
        >>> print(tenant_id)
        123e4567-e89b-12d3-a456-426614174000
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT get_current_tenant();")
        result = cursor.fetchone()
        if result and result[0]:
            # PostgreSQL returns UUID objects directly, convert to string first
            tenant_uuid = result[0]
            if isinstance(tenant_uuid, UUID):
                return tenant_uuid
            return UUID(str(tenant_uuid))
        return None


def enable_rls_bypass() -> None:
    """
    Enable RLS bypass for the current session (platform admin mode).

    This allows platform administrators to access all tenant data.
    Should only be used in admin panel contexts.

    WARNING: Use with extreme caution. This bypasses all tenant isolation.

    Example:
        >>> from apps.core.tenant_context import enable_rls_bypass
        >>> enable_rls_bypass()  # Now can access all tenant data

    Requirements: Requirement 4 - Admin Panel - Tenant Lifecycle Management
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")
        logger.warning("RLS bypass enabled - all tenant data is now accessible")


def disable_rls_bypass() -> None:
    """
    Disable RLS bypass for the current session.

    Re-enables normal tenant isolation after admin operations.

    Example:
        >>> from apps.core.tenant_context import disable_rls_bypass
        >>> disable_rls_bypass()  # Back to normal tenant isolation
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
        logger.debug("RLS bypass disabled - tenant isolation restored")


def is_rls_bypassed() -> bool:
    """
    Check if RLS bypass is currently enabled.

    Returns:
        True if RLS bypass is enabled, False otherwise.

    Example:
        >>> from apps.core.tenant_context import is_rls_bypassed
        >>> if is_rls_bypassed():
        ...     print("Running in admin mode")
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT is_rls_bypassed();")
        result = cursor.fetchone()
        return result[0] if result else False


@contextmanager
def tenant_context(tenant_id: Optional[UUID]):
    """
    Context manager for temporarily setting tenant context.

    Automatically restores the previous tenant context when exiting.

    Args:
        tenant_id: UUID of the tenant to set as context.

    Example:
        >>> from apps.core.tenant_context import tenant_context
        >>> from uuid import UUID
        >>>
        >>> tenant_id = UUID('123e4567-e89b-12d3-a456-426614174000')
        >>> with tenant_context(tenant_id):
        ...     # All queries here are scoped to this tenant
        ...     products = Product.objects.all()
        >>> # Original context is restored here

    Requirements: Requirement 1 - Multi-Tenant Architecture with Data Isolation
    """
    # Save current context
    previous_tenant = get_current_tenant()
    previous_bypass = is_rls_bypassed()

    try:
        # Set new context
        set_tenant_context(tenant_id)
        yield
    finally:
        # Restore previous context
        set_tenant_context(previous_tenant)
        if previous_bypass:
            enable_rls_bypass()
        else:
            disable_rls_bypass()


@contextmanager
def bypass_rls():
    """
    Context manager for temporarily bypassing RLS (admin operations).

    Automatically restores the previous RLS state when exiting.

    WARNING: Use with extreme caution. This bypasses all tenant isolation.

    Example:
        >>> from apps.core.tenant_context import bypass_rls
        >>>
        >>> with bypass_rls():
        ...     # Can access all tenant data here
        ...     all_tenants = Tenant.objects.all()
        >>> # RLS is restored here

    Requirements: Requirement 4 - Admin Panel - Tenant Lifecycle Management
    """
    # Save current bypass state
    previous_bypass = is_rls_bypassed()

    try:
        # Enable bypass
        enable_rls_bypass()
        yield
    finally:
        # Restore previous state
        if not previous_bypass:
            disable_rls_bypass()


def clear_tenant_context() -> None:
    """
    Clear the tenant context and disable RLS bypass.

    Useful for cleanup or resetting to a neutral state.

    Example:
        >>> from apps.core.tenant_context import clear_tenant_context
        >>> clear_tenant_context()
    """
    set_tenant_context(None)
    disable_rls_bypass()
    logger.debug("Tenant context cleared")
