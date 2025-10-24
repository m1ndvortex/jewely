"""
Notification services for creating and managing notifications.

This module provides utility functions for creating notifications,
checking user preferences, and managing notification delivery including email.
"""

import logging
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.utils import timezone

from .models import (
    EmailCampaign,
    EmailNotification,
    EmailTemplate,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)

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


# Email notification functions


def send_email_notification(
    user: User,
    template_name: str,
    context: Dict,
    subject: Optional[str] = None,
    from_email: Optional[str] = None,
    email_type: str = "TRANSACTIONAL",
    campaign_id: Optional[str] = None,
    scheduled_at: Optional[timezone.datetime] = None,
    create_in_app_notification: bool = True,
) -> Optional[EmailNotification]:
    """
    Send an email notification using a template.

    Args:
        user: User to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        subject: Optional override for email subject
        from_email: Optional override for from email
        email_type: Type of email (TRANSACTIONAL, MARKETING, SYSTEM)
        campaign_id: Optional campaign ID for tracking
        scheduled_at: Optional datetime to schedule email
        create_in_app_notification: Whether to create corresponding in-app notification

    Returns:
        EmailNotification instance or None if template not found
    """
    try:
        template = EmailTemplate.objects.get(name=template_name, is_active=True)
    except EmailTemplate.DoesNotExist:
        logger.error(f"Email template '{template_name}' not found or inactive")
        return None

    # Check user preferences - use a generic notification type for email delivery
    # For transactional emails, we should generally allow them regardless of preferences
    # But we'll check for a generic 'TRANSACTIONAL' type preference
    notification_type_for_preference = (
        "TRANSACTIONAL" if email_type == "TRANSACTIONAL" else "MARKETING"
    )
    if not should_send_notification(user, notification_type_for_preference, "EMAIL"):
        logger.info(f"Email notification skipped for user {user.username} due to preferences")
        return None

    # Render template
    rendered = template.render(context)
    email_subject = subject or rendered["subject"]
    html_body = rendered["html_body"]
    text_body = rendered.get("text_body")

    # Create in-app notification if requested
    in_app_notification = None
    if create_in_app_notification:
        in_app_notification = create_notification(
            user=user,
            title=email_subject,
            message=text_body or html_body[:200] + "...",  # Truncate HTML for in-app
            notification_type="INFO",
        )

    # Create email notification record
    email_notification = EmailNotification.objects.create(
        user=user,
        notification=in_app_notification,
        subject=email_subject,
        to_email=user.email,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        template_name=template_name,
        email_type=email_type,
        campaign_id=campaign_id,
        scheduled_at=scheduled_at,
    )

    # Send immediately if not scheduled
    if scheduled_at is None:
        _send_email_now(email_notification, html_body, text_body)
    else:
        # Schedule for later (would be handled by Celery task)
        logger.info(f"Email scheduled for {scheduled_at} for user {user.username}")

    return email_notification


def _send_email_now(
    email_notification: EmailNotification, html_body: str, text_body: Optional[str] = None
):
    """
    Internal function to send email immediately.
    """
    try:
        # Create email message
        msg = EmailMultiAlternatives(
            subject=email_notification.subject,
            body=text_body or html_body,
            from_email=email_notification.from_email,
            to=[email_notification.to_email],
        )

        if html_body:
            msg.attach_alternative(html_body, "text/html")

        # Send email
        msg.send()

        # Update status
        email_notification.update_status("SENT")

        logger.info(f"Email sent successfully to {email_notification.to_email}")

    except Exception as e:
        # Update status with error
        email_notification.update_status("FAILED", error_message=str(e))
        logger.error(f"Failed to send email to {email_notification.to_email}: {str(e)}")


def send_transactional_email(
    user: User, template_name: str, context: Dict, subject: Optional[str] = None
) -> Optional[EmailNotification]:
    """
    Send a transactional email (order confirmations, receipts, password resets, etc.).

    Args:
        user: User to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        subject: Optional override for email subject

    Returns:
        EmailNotification instance or None if failed
    """
    return send_email_notification(
        user=user,
        template_name=template_name,
        context=context,
        subject=subject,
        email_type="TRANSACTIONAL",
    )


def send_marketing_email(
    user: User, template_name: str, context: Dict, campaign_id: str, subject: Optional[str] = None
) -> Optional[EmailNotification]:
    """
    Send a marketing email.

    Args:
        user: User to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        campaign_id: Campaign ID for tracking
        subject: Optional override for email subject

    Returns:
        EmailNotification instance or None if failed
    """
    return send_email_notification(
        user=user,
        template_name=template_name,
        context=context,
        subject=subject,
        email_type="MARKETING",
        campaign_id=campaign_id,
        create_in_app_notification=False,  # Marketing emails don't create in-app notifications
    )


def send_system_email(
    user: User, template_name: str, context: Dict, subject: Optional[str] = None
) -> Optional[EmailNotification]:
    """
    Send a system email (maintenance notifications, security alerts, etc.).

    Args:
        user: User to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        subject: Optional override for email subject

    Returns:
        EmailNotification instance or None if failed
    """
    return send_email_notification(
        user=user,
        template_name=template_name,
        context=context,
        subject=subject,
        email_type="SYSTEM",
    )


def schedule_email(
    user: User,
    template_name: str,
    context: Dict,
    scheduled_at: timezone.datetime,
    email_type: str = "TRANSACTIONAL",
    subject: Optional[str] = None,
) -> Optional[EmailNotification]:
    """
    Schedule an email to be sent later.

    Args:
        user: User to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        scheduled_at: When to send the email
        email_type: Type of email
        subject: Optional override for email subject

    Returns:
        EmailNotification instance or None if failed
    """
    return send_email_notification(
        user=user,
        template_name=template_name,
        context=context,
        subject=subject,
        email_type=email_type,
        scheduled_at=scheduled_at,
    )


def send_bulk_email(
    users: List[User],
    template_name: str,
    context: Dict,
    email_type: str = "MARKETING",
    campaign_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> List[EmailNotification]:
    """
    Send bulk emails to multiple users.

    Args:
        users: List of users to send emails to
        template_name: Name of the email template
        context: Context variables for template rendering
        email_type: Type of email
        campaign_id: Optional campaign ID for tracking
        subject: Optional override for email subject

    Returns:
        List of EmailNotification instances
    """
    email_notifications = []

    for user in users:
        if user.email:  # Only send to users with email addresses
            email_notification = send_email_notification(
                user=user,
                template_name=template_name,
                context=context,
                subject=subject,
                email_type=email_type,
                campaign_id=campaign_id,
                create_in_app_notification=(email_type != "MARKETING"),
            )
            if email_notification:
                email_notifications.append(email_notification)

    logger.info(f"Sent {len(email_notifications)} bulk emails using template '{template_name}'")

    return email_notifications


def create_email_campaign(
    name: str,
    subject: str,
    template_name: str,
    created_by: User,
    target_users: Optional[List[User]] = None,
    target_roles: Optional[List[str]] = None,
    target_tenant_status: Optional[List[str]] = None,
    scheduled_at: Optional[timezone.datetime] = None,
) -> EmailCampaign:
    """
    Create an email marketing campaign.

    Args:
        name: Campaign name
        subject: Email subject
        template_name: Name of the email template
        created_by: User creating the campaign
        target_users: Specific users to target
        target_roles: User roles to target
        target_tenant_status: Tenant statuses to target
        scheduled_at: When to send the campaign

    Returns:
        EmailCampaign instance
    """
    try:
        template = EmailTemplate.objects.get(name=template_name, is_active=True)
    except EmailTemplate.DoesNotExist:
        raise ValueError(f"Email template '{template_name}' not found or inactive")

    campaign = EmailCampaign.objects.create(
        name=name,
        subject=subject,
        template=template,
        created_by=created_by,
        scheduled_at=scheduled_at,
        target_roles=target_roles or [],
        target_tenant_status=target_tenant_status or [],
    )

    if target_users:
        campaign.target_users.set(target_users)

    # Update total recipients count
    campaign.total_recipients = campaign.get_target_users().count()
    campaign.save()

    logger.info(f"Created email campaign '{name}' targeting {campaign.total_recipients} users")

    return campaign


def send_campaign(campaign: EmailCampaign, context: Optional[Dict] = None) -> int:
    """
    Send an email campaign to all targeted users.

    Args:
        campaign: EmailCampaign instance
        context: Optional context variables for template rendering

    Returns:
        Number of emails sent
    """
    if campaign.status != "DRAFT" and campaign.status != "SCHEDULED":
        raise ValueError(f"Campaign '{campaign.name}' cannot be sent (status: {campaign.status})")

    campaign.status = "SENDING"
    campaign.save()

    target_users = campaign.get_target_users()
    context = context or {}
    sent_count = 0

    for user in target_users:
        if user.email:
            email_notification = send_marketing_email(
                user=user,
                template_name=campaign.template.name,
                context=context,
                campaign_id=str(campaign.id),
                subject=campaign.subject,
            )
            if email_notification:
                sent_count += 1

    # Update campaign status and statistics
    campaign.status = "SENT"
    campaign.sent_at = timezone.now()
    campaign.emails_sent = sent_count
    campaign.save()

    logger.info(f"Campaign '{campaign.name}' sent to {sent_count} users")

    return sent_count


def process_scheduled_emails():
    """
    Process scheduled emails that are ready to be sent.
    This function should be called by a Celery task.

    Returns:
        Number of emails processed
    """
    now = timezone.now()

    # Process scheduled individual emails
    scheduled_emails = EmailNotification.objects.filter(status="PENDING", scheduled_at__lte=now)

    processed_count = 0

    for email_notification in scheduled_emails:
        try:
            # Get template and render
            template = EmailTemplate.objects.get(name=email_notification.template_name)
            context = {}  # Context would need to be stored or reconstructed
            rendered = template.render(context)

            _send_email_now(email_notification, rendered["html_body"], rendered.get("text_body"))
            processed_count += 1

        except Exception as e:
            email_notification.update_status("FAILED", error_message=str(e))
            logger.error(f"Failed to send scheduled email {email_notification.id}: {str(e)}")

    # Process scheduled campaigns
    scheduled_campaigns = EmailCampaign.objects.filter(status="SCHEDULED", scheduled_at__lte=now)

    for campaign in scheduled_campaigns:
        try:
            send_campaign(campaign)
        except Exception as e:
            campaign.status = "CANCELLED"
            campaign.save()
            logger.error(f"Failed to send scheduled campaign {campaign.id}: {str(e)}")

    logger.info(f"Processed {processed_count} scheduled emails")

    return processed_count


def track_email_event(
    message_id: str, event_type: str, timestamp: Optional[timezone.datetime] = None, **kwargs
):
    """
    Track email delivery events from webhook callbacks.

    Args:
        message_id: Email service provider message ID
        event_type: Type of event (sent, delivered, opened, clicked, bounced, failed)
        timestamp: Event timestamp
        **kwargs: Additional event data (bounce_reason, error_message, etc.)
    """
    try:
        email_notification = EmailNotification.objects.get(message_id=message_id)

        status_mapping = {
            "sent": "SENT",
            "delivered": "DELIVERED",
            "opened": "OPENED",
            "clicked": "CLICKED",
            "bounced": "BOUNCED",
            "failed": "FAILED",
            "complained": "COMPLAINED",
            "unsubscribed": "UNSUBSCRIBED",
        }

        status = status_mapping.get(event_type.lower())
        if status:
            email_notification.update_status(
                status=status,
                timestamp=timestamp,
                error_message=kwargs.get("error_message"),
                bounce_reason=kwargs.get("bounce_reason"),
            )

            # Update campaign statistics if this is a campaign email
            if email_notification.campaign_id:
                try:
                    campaign = EmailCampaign.objects.get(id=email_notification.campaign_id)
                    campaign.update_statistics()
                except EmailCampaign.DoesNotExist:
                    pass

            logger.info(f"Updated email {message_id} status to {status}")

    except EmailNotification.DoesNotExist:
        logger.warning(f"Email notification with message_id {message_id} not found")


def get_email_statistics(user: Optional[User] = None, campaign_id: Optional[str] = None) -> Dict:
    """
    Get email delivery statistics.

    Args:
        user: Optional user to filter statistics for
        campaign_id: Optional campaign ID to filter statistics for

    Returns:
        Dictionary with email statistics
    """
    queryset = EmailNotification.objects.all()

    if user:
        queryset = queryset.filter(user=user)

    if campaign_id:
        queryset = queryset.filter(campaign_id=campaign_id)

    stats = {
        "total": queryset.count(),
        "sent": queryset.filter(status__in=["SENT", "DELIVERED", "OPENED", "CLICKED"]).count(),
        "delivered": queryset.filter(status__in=["DELIVERED", "OPENED", "CLICKED"]).count(),
        "opened": queryset.filter(status__in=["OPENED", "CLICKED"]).count(),
        "clicked": queryset.filter(status="CLICKED").count(),
        "bounced": queryset.filter(status="BOUNCED").count(),
        "failed": queryset.filter(status="FAILED").count(),
    }

    # Calculate rates
    if stats["sent"] > 0:
        stats["delivery_rate"] = round((stats["delivered"] / stats["sent"]) * 100, 2)
        stats["open_rate"] = round((stats["opened"] / stats["sent"]) * 100, 2)
        stats["click_rate"] = round((stats["clicked"] / stats["sent"]) * 100, 2)
        stats["bounce_rate"] = round((stats["bounced"] / stats["sent"]) * 100, 2)
    else:
        stats["delivery_rate"] = 0
        stats["open_rate"] = 0
        stats["click_rate"] = 0
        stats["bounce_rate"] = 0

    return stats
