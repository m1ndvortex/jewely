"""
Notification services for creating and managing notifications.

This module provides utility functions for creating notifications,
checking user preferences, and managing notification delivery.
"""

import logging
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .models import Notification, NotificationPreference, NotificationTemplate

User = get_user_model()
logger = logging.getLogger(__name__)


def create_notification(
    user: User,
    title: str,
    message: str,
    notification_type: str = "INFO",
    action_url: Optional[str] = None,
    action_text: Optional[str] = None,
    expires_at: Optional[timezone.datetime] = None,
) -> Notification:
    """
    Create a new notification for a user.

    Args:
        user: User to receive the notification
        title: Notification title
        message: Notification message
        notification_type: Type of notification (default: 'INFO')
        action_url: Optional URL for action button
        action_text: Optional text for action button
        expires_at: Optional expiration datetime

    Returns:
        Created Notification instance

    Example:
        >>> from apps.notifications.services import create_notification
        >>> notification = create_notification(
        ...     user=user,
        ...     title='Low Stock Alert',
        ...     message='Gold Ring inventory is running low',
        ...     notification_type='LOW_STOCK',
        ...     action_url='/inventory/123/',
        ...     action_text='Restock Now'
        ... )
    """
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_text=action_text,
        expires_at=expires_at,
    )

    logger.info(
        f"Created notification '{title}' for user {user.username} " f"(type: {notification_type})"
    )

    return notification


def create_notification_from_template(
    template_name: str, user: User, context: Dict, expires_at: Optional[timezone.datetime] = None
) -> Optional[Notification]:
    """
    Create a notification using a template.

    Args:
        template_name: Name of the notification template
        user: User to receive the notification
        context: Context variables for template rendering
        expires_at: Optional expiration datetime

    Returns:
        Created Notification instance or None if template not found

    Example:
        >>> from apps.notifications.services import create_notification_from_template
        >>> notification = create_notification_from_template(
        ...     template_name='low_stock_alert',
        ...     user=user,
        ...     context={'item_name': 'Gold Ring', 'current_stock': 5}
        ... )
    """
    try:
        template = NotificationTemplate.objects.get(name=template_name, is_active=True)
    except NotificationTemplate.DoesNotExist:
        logger.error(f"Notification template '{template_name}' not found or inactive")
        return None

    # Render template with context
    rendered = template.render(context)

    # Create notification
    notification = Notification.objects.create(
        user=user,
        title=rendered["title"],
        message=rendered["message"],
        notification_type=template.notification_type,
        action_url=rendered.get("action_url"),
        action_text=rendered.get("action_text"),
        expires_at=expires_at,
    )

    logger.info(f"Created notification from template '{template_name}' for user {user.username}")

    return notification


def bulk_create_notifications(
    users: List[User],
    title: str,
    message: str,
    notification_type: str = "INFO",
    action_url: Optional[str] = None,
    action_text: Optional[str] = None,
    expires_at: Optional[timezone.datetime] = None,
) -> List[Notification]:
    """
    Create notifications for multiple users at once.

    Args:
        users: List of users to receive the notification
        title: Notification title
        message: Notification message
        notification_type: Type of notification (default: 'INFO')
        action_url: Optional URL for action button
        action_text: Optional text for action button
        expires_at: Optional expiration datetime

    Returns:
        List of created Notification instances

    Example:
        >>> from apps.notifications.services import bulk_create_notifications
        >>> notifications = bulk_create_notifications(
        ...     users=[user1, user2, user3],
        ...     title='System Maintenance',
        ...     message='System will be down for maintenance tonight',
        ...     notification_type='SYSTEM'
        ... )
    """
    notifications = []

    for user in users:
        notification = Notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_text=action_text,
            expires_at=expires_at,
        )
        notifications.append(notification)

    # Bulk create for better performance
    created_notifications = Notification.objects.bulk_create(notifications)

    logger.info(
        f"Created {len(created_notifications)} notifications of type '{notification_type}' "
        f"for {len(users)} users"
    )

    return created_notifications


def get_user_notifications(
    user: User,
    unread_only: bool = False,
    notification_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Notification]:
    """
    Get notifications for a user with optional filtering.

    Args:
        user: User to get notifications for
        unread_only: If True, only return unread notifications
        notification_type: Optional filter by notification type
        limit: Optional limit on number of notifications returned

    Returns:
        List of Notification instances

    Example:
        >>> from apps.notifications.services import get_user_notifications
        >>> unread_notifications = get_user_notifications(
        ...     user=user,
        ...     unread_only=True,
        ...     limit=10
        ... )
    """
    queryset = user.notifications.all()

    if unread_only:
        queryset = queryset.filter(is_read=False)

    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)

    # Filter out expired notifications
    queryset = queryset.filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
    )

    if limit:
        queryset = queryset[:limit]

    return list(queryset)


def get_unread_count(user: User) -> int:
    """
    Get count of unread notifications for a user.

    Args:
        user: User to count notifications for

    Returns:
        Number of unread notifications

    Example:
        >>> from apps.notifications.services import get_unread_count
        >>> count = get_unread_count(user)
        >>> print(f"You have {count} unread notifications")
    """
    return (
        user.notifications.filter(is_read=False)
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()))
        .count()
    )


def mark_notifications_as_read(user: User, notification_ids: Optional[List[int]] = None) -> int:
    """
    Mark notifications as read for a user.

    Args:
        user: User whose notifications to mark as read
        notification_ids: Optional list of specific notification IDs to mark as read.
                         If None, marks all unread notifications as read.

    Returns:
        Number of notifications marked as read

    Example:
        >>> from apps.notifications.services import mark_notifications_as_read
        >>> # Mark all unread notifications as read
        >>> count = mark_notifications_as_read(user)
        >>>
        >>> # Mark specific notifications as read
        >>> count = mark_notifications_as_read(user, [1, 2, 3])
    """
    queryset = user.notifications.filter(is_read=False)

    if notification_ids:
        queryset = queryset.filter(id__in=notification_ids)

    count = queryset.update(is_read=True, read_at=timezone.now())

    logger.info(f"Marked {count} notifications as read for user {user.username}")

    return count


def cleanup_expired_notifications() -> int:
    """
    Clean up expired notifications from the database.

    This function should be called periodically (e.g., via a Celery task)
    to remove expired notifications and keep the database clean.

    Returns:
        Number of notifications deleted

    Example:
        >>> from apps.notifications.services import cleanup_expired_notifications
        >>> deleted_count = cleanup_expired_notifications()
        >>> print(f"Cleaned up {deleted_count} expired notifications")
    """
    deleted_count, _ = Notification.objects.filter(expires_at__lt=timezone.now()).delete()

    logger.info(f"Cleaned up {deleted_count} expired notifications")

    return deleted_count


def get_user_preference(
    user: User, notification_type: str, channel: str
) -> Optional[NotificationPreference]:
    """
    Get user's preference for a specific notification type and channel.

    Args:
        user: User to get preference for
        notification_type: Type of notification
        channel: Delivery channel (IN_APP, EMAIL, SMS, PUSH)

    Returns:
        NotificationPreference instance or None if not found

    Example:
        >>> from apps.notifications.services import get_user_preference
        >>> preference = get_user_preference(
        ...     user=user,
        ...     notification_type='LOW_STOCK',
        ...     channel='EMAIL'
        ... )
        >>> if preference and preference.is_enabled:
        ...     print("User wants email notifications for low stock")
    """
    try:
        return NotificationPreference.objects.get(
            user=user, notification_type=notification_type, channel=channel
        )
    except NotificationPreference.DoesNotExist:
        return None


def should_send_notification(user: User, notification_type: str, channel: str) -> bool:
    """
    Check if a notification should be sent to a user based on their preferences.

    Args:
        user: User to check preferences for
        notification_type: Type of notification
        channel: Delivery channel (IN_APP, EMAIL, SMS, PUSH)

    Returns:
        True if notification should be sent, False otherwise

    Example:
        >>> from apps.notifications.services import should_send_notification
        >>> if should_send_notification(user, 'LOW_STOCK', 'EMAIL'):
        ...     send_email_notification(user, notification)
    """
    preference = get_user_preference(user, notification_type, channel)

    # If no preference exists, default to enabled for IN_APP, disabled for others
    if preference is None:
        return channel == "IN_APP"

    # Check if preference is enabled
    if not preference.is_enabled:
        return False

    # Check quiet hours for non-critical notifications
    if notification_type not in ["ERROR", "SYSTEM"] and preference.is_in_quiet_hours():
        return False

    return True
