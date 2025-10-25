"""
Notification services for creating and managing notifications.

This module provides utility functions for creating notifications,
checking user preferences, and managing notification delivery including email and SMS.
"""

import logging
import uuid
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.utils import timezone

from .models import (
    CampaignAnalytics,
    CommunicationLog,
    CustomerSegment,
    EmailCampaign,
    EmailNotification,
    EmailTemplate,
    Notification,
    NotificationPreference,
    NotificationTemplate,
    SMSCampaign,
    SMSNotification,
    SMSOptOut,
    SMSTemplate,
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


# SMS notification functions


def _get_twilio_client():
    """
    Get Twilio client instance.
    """
    try:
        from twilio.rest import Client

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)

        if not account_sid or not auth_token:
            logger.error("Twilio credentials not configured")
            return None

        return Client(account_sid, auth_token)
    except ImportError:
        logger.error("Twilio library not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")
        return None


def _normalize_phone_number(phone_number: str) -> str:
    """
    Normalize phone number to E.164 format.

    Args:
        phone_number: Phone number to normalize

    Returns:
        Normalized phone number in E.164 format
    """
    import re

    # If it already starts with +, return as is (already normalized)
    if phone_number.startswith("+"):
        return phone_number

    # Remove all non-digit characters
    digits_only = re.sub(r"\D", "", phone_number)

    # If it starts with 1 and has 11 digits, it's likely US/Canada
    if len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"

    # If it has 10 digits, assume US/Canada and add +1
    elif len(digits_only) == 10:
        return f"+1{digits_only}"

    # Otherwise, add + and return
    else:
        return f"+{digits_only}"


def is_user_opted_out_sms(user: User, sms_type: str = "MARKETING") -> bool:
    """
    Check if user has opted out of SMS notifications.

    Args:
        user: User to check
        sms_type: Type of SMS to check (TRANSACTIONAL, MARKETING, SYSTEM, ALERT)

    Returns:
        True if user is opted out, False otherwise
    """
    try:
        opt_out = SMSOptOut.objects.get(user=user)
        return opt_out.is_opted_out_for_type(sms_type)
    except SMSOptOut.DoesNotExist:
        # If no opt-out record exists, only marketing is opted out by default
        return sms_type == "MARKETING"


def opt_out_user_sms(
    user: User, sms_type: str = "MARKETING", reason: Optional[str] = None
) -> SMSOptOut:
    """
    Opt user out of SMS notifications.

    Args:
        user: User to opt out
        sms_type: Type of SMS to opt out of
        reason: Optional reason for opting out

    Returns:
        SMSOptOut instance
    """
    opt_out, created = SMSOptOut.objects.get_or_create(user=user, defaults={"reason": reason})

    # Set the appropriate opt-out flag
    if sms_type == "TRANSACTIONAL":
        opt_out.transactional_opt_out = True
    elif sms_type == "MARKETING":
        opt_out.marketing_opt_out = True
    elif sms_type == "SYSTEM":
        opt_out.system_opt_out = True
    elif sms_type == "ALERT":
        opt_out.alert_opt_out = True

    opt_out.save()

    logger.info(f"User {user.username} opted out of {sms_type} SMS")

    return opt_out


def opt_in_user_sms(user: User, sms_type: str = "MARKETING") -> Optional[SMSOptOut]:
    """
    Opt user back in to SMS notifications.

    Args:
        user: User to opt in
        sms_type: Type of SMS to opt in to

    Returns:
        SMSOptOut instance or None if no opt-out record exists
    """
    try:
        opt_out = SMSOptOut.objects.get(user=user)

        # Clear the appropriate opt-out flag
        if sms_type == "TRANSACTIONAL":
            opt_out.transactional_opt_out = False
        elif sms_type == "MARKETING":
            opt_out.marketing_opt_out = False
        elif sms_type == "SYSTEM":
            opt_out.system_opt_out = False
        elif sms_type == "ALERT":
            opt_out.alert_opt_out = False

        opt_out.save()

        logger.info(f"User {user.username} opted in to {sms_type} SMS")

        return opt_out

    except SMSOptOut.DoesNotExist:
        logger.info(f"User {user.username} was not opted out of {sms_type} SMS")
        return None


def send_sms_notification(
    user: User,
    message: str,
    sms_type: str = "TRANSACTIONAL",
    template_name: Optional[str] = None,
    campaign_id: Optional[str] = None,
    scheduled_at: Optional[timezone.datetime] = None,
    create_in_app_notification: bool = True,
) -> Optional[SMSNotification]:
    """
    Send an SMS notification to a user.

    Args:
        user: User to send SMS to
        message: SMS message content
        sms_type: Type of SMS (TRANSACTIONAL, MARKETING, SYSTEM, ALERT)
        template_name: Optional template name used
        campaign_id: Optional campaign ID for tracking
        scheduled_at: Optional datetime to schedule SMS
        create_in_app_notification: Whether to create corresponding in-app notification

    Returns:
        SMSNotification instance or None if failed
    """
    # Check if user has a phone number
    if not user.phone:
        logger.warning(f"User {user.username} has no phone number for SMS")
        return None

    # Check if user is opted out
    if is_user_opted_out_sms(user, sms_type):
        logger.info(f"SMS skipped for user {user.username} - opted out of {sms_type}")
        return None

    # Check user preferences
    if not should_send_notification(user, sms_type, "SMS"):
        logger.info(f"SMS skipped for user {user.username} due to preferences")
        return None

    # Normalize phone number
    try:
        normalized_phone = _normalize_phone_number(user.phone)
    except Exception as e:
        logger.error(f"Failed to normalize phone number {user.phone}: {str(e)}")
        return None

    # Create in-app notification if requested
    in_app_notification = None
    if create_in_app_notification:
        in_app_notification = create_notification(
            user=user,
            title="SMS Notification",
            message=message[:200] + "..." if len(message) > 200 else message,
            notification_type="INFO",
        )

    # Create SMS notification record
    sms_notification = SMSNotification.objects.create(
        user=user,
        notification=in_app_notification,
        message=message,
        to_phone=normalized_phone,
        from_phone=getattr(settings, "TWILIO_PHONE_NUMBER", None),
        template_name=template_name,
        sms_type=sms_type,
        campaign_id=campaign_id,
        scheduled_at=scheduled_at,
    )

    # Send immediately if not scheduled
    if scheduled_at is None:
        _send_sms_now(sms_notification)
    else:
        logger.info(f"SMS scheduled for {scheduled_at} for user {user.username}")

    return sms_notification


def _send_sms_now(sms_notification: SMSNotification):
    """
    Internal function to send SMS immediately using Twilio.
    """
    client = _get_twilio_client()
    if not client:
        sms_notification.update_status("FAILED", error_message="Twilio client not available")
        return

    try:
        # Send SMS via Twilio
        message = client.messages.create(
            body=sms_notification.message,
            from_=sms_notification.from_phone or getattr(settings, "TWILIO_PHONE_NUMBER"),
            to=sms_notification.to_phone,
        )

        # Update SMS notification with Twilio response
        sms_notification.message_sid = message.sid
        sms_notification.update_status(
            "SENT" if message.status in ["queued", "sent"] else "FAILED",
            price=float(message.price) if message.price else None,
            price_unit=message.price_unit,
        )

        logger.info(f"SMS sent successfully to {sms_notification.to_phone}, SID: {message.sid}")

    except Exception as e:
        # Update status with error
        sms_notification.update_status("FAILED", error_message=str(e))
        logger.error(f"Failed to send SMS to {sms_notification.to_phone}: {str(e)}")


def send_sms_from_template(
    user: User,
    template_name: str,
    context: Dict,
    sms_type: str = "TRANSACTIONAL",
    campaign_id: Optional[str] = None,
    scheduled_at: Optional[timezone.datetime] = None,
) -> Optional[SMSNotification]:
    """
    Send an SMS using a template.

    Args:
        user: User to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering
        sms_type: Type of SMS
        campaign_id: Optional campaign ID for tracking
        scheduled_at: Optional datetime to schedule SMS

    Returns:
        SMSNotification instance or None if failed
    """
    try:
        template = SMSTemplate.objects.get(name=template_name, is_active=True)
    except SMSTemplate.DoesNotExist:
        logger.error(f"SMS template '{template_name}' not found or inactive")
        return None

    # Render template
    rendered = template.render(context)
    message = rendered["message"]

    # Ensure message is within SMS length limits
    if len(message) > 1600:
        logger.warning(f"SMS message truncated from {len(message)} to 1600 characters")
        message = message[:1597] + "..."

    return send_sms_notification(
        user=user,
        message=message,
        sms_type=sms_type,
        template_name=template_name,
        campaign_id=campaign_id,
        scheduled_at=scheduled_at,
    )


def send_transactional_sms(
    user: User, template_name: str, context: Dict
) -> Optional[SMSNotification]:
    """
    Send a transactional SMS (order confirmations, appointments, etc.).

    Args:
        user: User to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering

    Returns:
        SMSNotification instance or None if failed
    """
    return send_sms_from_template(
        user=user,
        template_name=template_name,
        context=context,
        sms_type="TRANSACTIONAL",
    )


def send_alert_sms(user: User, template_name: str, context: Dict) -> Optional[SMSNotification]:
    """
    Send an alert SMS (low stock, payment reminders, etc.).

    Args:
        user: User to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering

    Returns:
        SMSNotification instance or None if failed
    """
    return send_sms_from_template(
        user=user,
        template_name=template_name,
        context=context,
        sms_type="ALERT",
    )


def send_marketing_sms(
    user: User, template_name: str, context: Dict, campaign_id: str
) -> Optional[SMSNotification]:
    """
    Send a marketing SMS.

    Args:
        user: User to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering
        campaign_id: Campaign ID for tracking

    Returns:
        SMSNotification instance or None if failed
    """
    return send_sms_from_template(
        user=user,
        template_name=template_name,
        context=context,
        sms_type="MARKETING",
        campaign_id=campaign_id,
    )


def schedule_sms(
    user: User,
    template_name: str,
    context: Dict,
    scheduled_at: timezone.datetime,
    sms_type: str = "TRANSACTIONAL",
) -> Optional[SMSNotification]:
    """
    Schedule an SMS to be sent later.

    Args:
        user: User to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering
        scheduled_at: When to send the SMS
        sms_type: Type of SMS

    Returns:
        SMSNotification instance or None if failed
    """
    return send_sms_from_template(
        user=user,
        template_name=template_name,
        context=context,
        sms_type=sms_type,
        scheduled_at=scheduled_at,
    )


def send_bulk_sms(
    users: List[User],
    template_name: str,
    context: Dict,
    sms_type: str = "MARKETING",
    campaign_id: Optional[str] = None,
) -> List[SMSNotification]:
    """
    Send bulk SMS to multiple users.

    Args:
        users: List of users to send SMS to
        template_name: Name of the SMS template
        context: Context variables for template rendering
        sms_type: Type of SMS
        campaign_id: Optional campaign ID for tracking

    Returns:
        List of SMSNotification instances
    """
    sms_notifications = []

    for user in users:
        if user.phone:  # Only send to users with phone numbers
            sms_notification = send_sms_from_template(
                user=user,
                template_name=template_name,
                context=context,
                sms_type=sms_type,
                campaign_id=campaign_id,
            )
            if sms_notification:
                sms_notifications.append(sms_notification)

    logger.info(f"Sent {len(sms_notifications)} bulk SMS using template '{template_name}'")

    return sms_notifications


def create_sms_campaign(
    name: str,
    template_name: str,
    created_by: User,
    target_users: Optional[List[User]] = None,
    target_roles: Optional[List[str]] = None,
    target_tenant_status: Optional[List[str]] = None,
    scheduled_at: Optional[timezone.datetime] = None,
) -> SMSCampaign:
    """
    Create an SMS marketing campaign.

    Args:
        name: Campaign name
        template_name: Name of the SMS template
        created_by: User creating the campaign
        target_users: Specific users to target
        target_roles: User roles to target
        target_tenant_status: Tenant statuses to target
        scheduled_at: When to send the campaign

    Returns:
        SMSCampaign instance
    """
    try:
        template = SMSTemplate.objects.get(name=template_name, is_active=True)
    except SMSTemplate.DoesNotExist:
        raise ValueError(f"SMS template '{template_name}' not found or inactive")

    campaign = SMSCampaign.objects.create(
        name=name,
        template=template,
        created_by=created_by,
        scheduled_at=scheduled_at,
        target_roles=target_roles or [],
        target_tenant_status=target_tenant_status or [],
    )

    if target_users:
        campaign.target_users.set(target_users)

    # Update total recipients count
    campaign.total_recipients = (
        campaign.get_target_users().filter(phone__isnull=False).exclude(phone="").count()
    )
    campaign.save()

    logger.info(f"Created SMS campaign '{name}' targeting {campaign.total_recipients} users")

    return campaign


def send_sms_campaign(campaign: SMSCampaign, context: Optional[Dict] = None) -> int:
    """
    Send an SMS campaign to all targeted users.

    Args:
        campaign: SMSCampaign instance
        context: Optional context variables for template rendering

    Returns:
        Number of SMS sent
    """
    if campaign.status != "DRAFT" and campaign.status != "SCHEDULED":
        raise ValueError(f"Campaign '{campaign.name}' cannot be sent (status: {campaign.status})")

    campaign.status = "SENDING"
    campaign.save()

    target_users = campaign.get_target_users().filter(phone__isnull=False).exclude(phone="")
    context = context or {}
    sent_count = 0

    for user in target_users:
        sms_notification = send_sms_from_template(
            user=user,
            template_name=campaign.template.name,
            context=context,
            sms_type="MARKETING",
            campaign_id=str(campaign.id),
        )
        if sms_notification:
            sent_count += 1

    # Update campaign status and statistics
    campaign.status = "SENT"
    campaign.sent_at = timezone.now()
    campaign.sms_sent = sent_count
    campaign.save()

    logger.info(f"SMS campaign '{campaign.name}' sent to {sent_count} users")

    return sent_count


def process_scheduled_sms():
    """
    Process scheduled SMS that are ready to be sent.
    This function should be called by a Celery task.

    Returns:
        Number of SMS processed
    """
    now = timezone.now()

    # Process scheduled individual SMS
    scheduled_sms = SMSNotification.objects.filter(status="PENDING", scheduled_at__lte=now)

    processed_count = 0

    for sms_notification in scheduled_sms:
        try:
            _send_sms_now(sms_notification)
            processed_count += 1
        except Exception as e:
            sms_notification.update_status("FAILED", error_message=str(e))
            logger.error(f"Failed to send scheduled SMS {sms_notification.id}: {str(e)}")

    # Process scheduled campaigns
    scheduled_campaigns = SMSCampaign.objects.filter(status="SCHEDULED", scheduled_at__lte=now)

    for campaign in scheduled_campaigns:
        try:
            send_sms_campaign(campaign)
        except Exception as e:
            campaign.status = "CANCELLED"
            campaign.save()
            logger.error(f"Failed to send scheduled SMS campaign {campaign.id}: {str(e)}")

    logger.info(f"Processed {processed_count} scheduled SMS")

    return processed_count


def track_sms_event(
    message_sid: str, event_type: str, timestamp: Optional[timezone.datetime] = None, **kwargs
):
    """
    Track SMS delivery events from Twilio webhook callbacks.

    Args:
        message_sid: Twilio message SID
        event_type: Type of event (sent, delivered, failed, undelivered)
        timestamp: Event timestamp
        **kwargs: Additional event data (error_code, error_message, etc.)
    """
    try:
        sms_notification = SMSNotification.objects.get(message_sid=message_sid)

        status_mapping = {
            "queued": "QUEUED",
            "sent": "SENT",
            "delivered": "DELIVERED",
            "failed": "FAILED",
            "undelivered": "UNDELIVERED",
        }

        status = status_mapping.get(event_type.lower())
        if status:
            sms_notification.update_status(
                status=status,
                timestamp=timestamp,
                error_message=kwargs.get("error_message"),
                error_code=kwargs.get("error_code"),
            )

            # Update campaign statistics if this is a campaign SMS
            if sms_notification.campaign_id:
                try:
                    campaign = SMSCampaign.objects.get(id=sms_notification.campaign_id)
                    campaign.update_statistics()
                except SMSCampaign.DoesNotExist:
                    pass

            logger.info(f"Updated SMS {message_sid} status to {status}")

    except SMSNotification.DoesNotExist:
        logger.warning(f"SMS notification with message_sid {message_sid} not found")


def get_sms_statistics(user: Optional[User] = None, campaign_id: Optional[str] = None) -> Dict:
    """
    Get SMS delivery statistics.

    Args:
        user: Optional user to filter statistics for
        campaign_id: Optional campaign ID to filter statistics for

    Returns:
        Dictionary with SMS statistics
    """
    queryset = SMSNotification.objects.all()

    if user:
        queryset = queryset.filter(user=user)

    if campaign_id:
        queryset = queryset.filter(campaign_id=campaign_id)

    stats = {
        "total": queryset.count(),
        "sent": queryset.filter(status__in=["SENT", "DELIVERED"]).count(),
        "delivered": queryset.filter(status="DELIVERED").count(),
        "failed": queryset.filter(status__in=["FAILED", "UNDELIVERED"]).count(),
        "pending": queryset.filter(status="PENDING").count(),
        "queued": queryset.filter(status="QUEUED").count(),
    }

    # Calculate rates
    if stats["sent"] > 0:
        stats["delivery_rate"] = round((stats["delivered"] / stats["sent"]) * 100, 2)
        stats["failure_rate"] = round((stats["failed"] / stats["sent"]) * 100, 2)
    else:
        stats["delivery_rate"] = 0
        stats["failure_rate"] = 0

    # Calculate total cost
    total_cost = queryset.aggregate(total=models.Sum("price"))["total"] or 0
    stats["total_cost"] = float(total_cost)

    return stats


# Customer Segmentation Services


def create_customer_segment(
    name: str,
    description: str = "",
    segment_type: str = "STATIC",
    criteria: Optional[Dict] = None,
    customers: Optional[List] = None,
    created_by: Optional[User] = None,
) -> "CustomerSegment":
    """
    Create a new customer segment.

    Args:
        name: Segment name
        description: Segment description
        segment_type: Type of segment (STATIC or DYNAMIC)
        criteria: Segmentation criteria for dynamic segments
        customers: List of customers for static segments
        created_by: User creating the segment

    Returns:
        CustomerSegment instance

    Example:
        >>> from apps.notifications.services import create_customer_segment
        >>> segment = create_customer_segment(
        ...     name="VIP Customers",
        ...     description="High-value customers",
        ...     segment_type="DYNAMIC",
        ...     criteria={
        ...         "min_total_purchases": 10000,
        ...         "loyalty_tiers": ["Gold", "Platinum"]
        ...     }
        ... )
    """
    from .models import CustomerSegment

    segment = CustomerSegment.objects.create(
        name=name,
        description=description,
        segment_type=segment_type,
        criteria=criteria or {},
        created_by=created_by,
    )

    if segment_type == "STATIC" and customers:
        segment.customers.set(customers)

    # Update customer count
    segment.update_customer_count()

    logger.info(f"Created customer segment '{name}' with {segment.customer_count} customers")

    return segment


def update_dynamic_segments():
    """
    Update all dynamic customer segments by recalculating their customer counts.
    This should be called periodically via a Celery task.

    Returns:
        Number of segments updated
    """
    from .models import CustomerSegment

    dynamic_segments = CustomerSegment.objects.filter(segment_type="DYNAMIC", is_active=True)
    updated_count = 0

    for segment in dynamic_segments:
        old_count = segment.customer_count
        segment.update_customer_count()

        if segment.customer_count != old_count:
            logger.info(
                f"Updated segment '{segment.name}': {old_count} -> {segment.customer_count} customers"
            )

        updated_count += 1

    logger.info(f"Updated {updated_count} dynamic customer segments")
    return updated_count


def get_segment_customers(segment_id: str, limit: Optional[int] = None):
    """
    Get customers in a specific segment.

    Args:
        segment_id: Segment UUID
        limit: Optional limit on number of customers returned

    Returns:
        QuerySet of customers in the segment
    """
    from .models import CustomerSegment

    try:
        segment = CustomerSegment.objects.get(id=segment_id)
        customers = segment.get_customers()

        if limit:
            customers = customers[:limit]

        return customers
    except CustomerSegment.DoesNotExist:
        logger.error(f"Customer segment {segment_id} not found")
        return None


# Campaign Analytics Services


def create_campaign_analytics(
    campaign_id: str,
    campaign_name: str,
    campaign_type: str,
    segment: Optional["CustomerSegment"] = None,
    campaign_sent_at: Optional[timezone.datetime] = None,
) -> "CampaignAnalytics":
    """
    Create campaign analytics record.

    Args:
        campaign_id: Campaign identifier
        campaign_name: Campaign name
        campaign_type: Type of campaign (EMAIL, SMS, MIXED)
        segment: Customer segment targeted
        campaign_sent_at: When campaign was sent

    Returns:
        CampaignAnalytics instance
    """
    from .models import CampaignAnalytics

    analytics = CampaignAnalytics.objects.create(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        campaign_type=campaign_type,
        segment=segment,
        campaign_sent_at=campaign_sent_at or timezone.now(),
    )

    logger.info(f"Created analytics record for campaign '{campaign_name}'")
    return analytics


def update_campaign_analytics(campaign_id: str) -> Optional["CampaignAnalytics"]:
    """
    Update campaign analytics with latest metrics.

    Args:
        campaign_id: Campaign identifier

    Returns:
        Updated CampaignAnalytics instance or None if not found
    """
    from .models import CampaignAnalytics

    try:
        analytics = CampaignAnalytics.objects.get(campaign_id=campaign_id)

        # Update email metrics
        if analytics.campaign_type in ["EMAIL", "MIXED"]:
            email_stats = get_email_statistics(campaign_id=campaign_id)
            analytics.total_recipients = email_stats["total"]
            analytics.messages_sent = email_stats["sent"]
            analytics.messages_delivered = email_stats["delivered"]
            analytics.emails_opened = email_stats["opened"]
            analytics.emails_clicked = email_stats["clicked"]
            analytics.emails_bounced = email_stats["bounced"]
            analytics.messages_failed = email_stats["failed"]

        # Update SMS metrics
        if analytics.campaign_type in ["SMS", "MIXED"]:
            sms_stats = get_sms_statistics(campaign_id=campaign_id)
            if analytics.campaign_type == "SMS":
                analytics.total_recipients = sms_stats["total"]
                analytics.messages_sent = sms_stats["sent"]
                analytics.messages_delivered = sms_stats["delivered"]
                analytics.messages_failed = sms_stats["failed"]
            analytics.total_cost = sms_stats["total_cost"]

        # Calculate rates
        analytics.calculate_rates()

        logger.info(f"Updated analytics for campaign '{analytics.campaign_name}'")
        return analytics

    except CampaignAnalytics.DoesNotExist:
        logger.error(f"Campaign analytics for {campaign_id} not found")
        return None


def track_campaign_conversion(
    campaign_id: str,
    conversion_value: Optional[float] = None,
    customer_id: Optional[str] = None,
) -> bool:
    """
    Track a conversion for a campaign.

    Args:
        campaign_id: Campaign identifier
        conversion_value: Value of the conversion
        customer_id: Customer who converted

    Returns:
        True if conversion was tracked, False otherwise
    """
    from .models import CampaignAnalytics, CommunicationLog

    try:
        analytics = CampaignAnalytics.objects.get(campaign_id=campaign_id)
        analytics.conversions += 1

        if conversion_value:
            analytics.conversion_value += conversion_value

        # Save the updated conversion data first
        analytics.save(update_fields=["conversions", "conversion_value"])

        # Then calculate and save the rates
        analytics.calculate_rates()

        # Update communication log if customer is provided
        if customer_id:
            try:
                from apps.crm.models import Customer

                customer = Customer.objects.get(id=customer_id)

                # Find the communication log entry for this campaign and customer
                comm_log = CommunicationLog.objects.filter(
                    customer=customer, campaign_id=campaign_id
                ).first()

                if comm_log:
                    comm_log.resulted_in_conversion = True
                    comm_log.conversion_value = conversion_value
                    comm_log.save(update_fields=["resulted_in_conversion", "conversion_value"])

            except Customer.DoesNotExist:
                pass

        logger.info(
            f"Tracked conversion for campaign '{analytics.campaign_name}': ${conversion_value}"
        )
        return True

    except CampaignAnalytics.DoesNotExist:
        logger.error(f"Campaign analytics for {campaign_id} not found")
        return False


def get_campaign_performance_report(
    start_date: Optional[timezone.datetime] = None,
    end_date: Optional[timezone.datetime] = None,
    campaign_type: Optional[str] = None,
) -> Dict:
    """
    Get campaign performance report.

    Args:
        start_date: Start date for report
        end_date: End date for report
        campaign_type: Filter by campaign type

    Returns:
        Dictionary with campaign performance metrics
    """
    from .models import CampaignAnalytics

    queryset = CampaignAnalytics.objects.all()

    if start_date:
        queryset = queryset.filter(campaign_sent_at__gte=start_date)

    if end_date:
        queryset = queryset.filter(campaign_sent_at__lte=end_date)

    if campaign_type:
        queryset = queryset.filter(campaign_type=campaign_type)

    # Aggregate metrics
    aggregates = queryset.aggregate(
        total_campaigns=models.Count("id"),
        total_recipients=models.Sum("total_recipients"),
        total_sent=models.Sum("messages_sent"),
        total_delivered=models.Sum("messages_delivered"),
        total_opened=models.Sum("emails_opened"),
        total_clicked=models.Sum("emails_clicked"),
        total_conversions=models.Sum("conversions"),
        total_conversion_value=models.Sum("conversion_value"),
        total_cost=models.Sum("total_cost"),
    )

    # Calculate overall rates
    report = {
        "total_campaigns": aggregates["total_campaigns"] or 0,
        "total_recipients": aggregates["total_recipients"] or 0,
        "total_sent": aggregates["total_sent"] or 0,
        "total_delivered": aggregates["total_delivered"] or 0,
        "total_opened": aggregates["total_opened"] or 0,
        "total_clicked": aggregates["total_clicked"] or 0,
        "total_conversions": aggregates["total_conversions"] or 0,
        "total_conversion_value": float(aggregates["total_conversion_value"] or 0),
        "total_cost": float(aggregates["total_cost"] or 0),
    }

    # Calculate rates
    if report["total_sent"] > 0:
        report["overall_delivery_rate"] = round(
            (report["total_delivered"] / report["total_sent"]) * 100, 2
        )
        report["overall_conversion_rate"] = round(
            (report["total_conversions"] / report["total_sent"]) * 100, 2
        )
    else:
        report["overall_delivery_rate"] = 0
        report["overall_conversion_rate"] = 0

    if report["total_delivered"] > 0:
        report["overall_open_rate"] = round(
            (report["total_opened"] / report["total_delivered"]) * 100, 2
        )
    else:
        report["overall_open_rate"] = 0

    if report["total_opened"] > 0:
        report["overall_click_rate"] = round(
            (report["total_clicked"] / report["total_opened"]) * 100, 2
        )
    else:
        report["overall_click_rate"] = 0

    if report["total_cost"] > 0:
        report["overall_roi"] = round(
            ((report["total_conversion_value"] - report["total_cost"]) / report["total_cost"])
            * 100,
            2,
        )
    else:
        report["overall_roi"] = 0

    return report


# Communication Logging Services


def log_customer_communication(
    customer,
    communication_type: str,
    direction: str,
    subject: str = "",
    content: str = "",
    campaign_id: str = "",
    email_notification: Optional[EmailNotification] = None,
    sms_notification: Optional[SMSNotification] = None,
    created_by: Optional[User] = None,
) -> "CommunicationLog":
    """
    Log a customer communication.

    Args:
        customer: Customer instance
        communication_type: Type of communication (EMAIL, SMS, etc.)
        direction: Direction (OUTBOUND, INBOUND, INTERNAL)
        subject: Subject or title
        content: Content or summary
        campaign_id: Campaign ID if applicable
        email_notification: Related email notification
        sms_notification: Related SMS notification
        created_by: User who logged this

    Returns:
        CommunicationLog instance
    """
    from .models import CommunicationLog

    comm_log = CommunicationLog.objects.create(
        customer=customer,
        communication_type=communication_type,
        direction=direction,
        subject=subject,
        content=content,
        campaign_id=campaign_id,
        email_notification=email_notification,
        sms_notification=sms_notification,
        created_by=created_by,
    )

    logger.info(f"Logged {communication_type} communication with {customer.get_full_name()}")
    return comm_log


def get_customer_communication_history(
    customer,
    communication_type: Optional[str] = None,
    limit: Optional[int] = None,
) -> List["CommunicationLog"]:
    """
    Get communication history for a customer.

    Args:
        customer: Customer instance
        communication_type: Filter by communication type
        limit: Limit number of results

    Returns:
        List of CommunicationLog instances
    """
    from .models import CommunicationLog

    queryset = CommunicationLog.objects.filter(customer=customer)

    if communication_type:
        queryset = queryset.filter(communication_type=communication_type)

    if limit:
        queryset = queryset[:limit]

    return list(queryset)


def _send_email_to_customer(customer, template_name, context, campaign_id, subject, created_by):
    """Send email campaign to a single customer."""
    if not customer.email:
        return False
    
    user = User.objects.filter(email=customer.email).first()
    if not user:
        return False
    
    email_notification = send_marketing_email(
        user=user,
        template_name=template_name,
        context={**context, "customer": customer},
        campaign_id=campaign_id,
        subject=subject,
    )
    
    if email_notification:
        log_customer_communication(
            customer=customer,
            communication_type="EMAIL",
            direction="OUTBOUND",
            subject=subject,
            content=f"Marketing email sent using template: {template_name}",
            campaign_id=campaign_id,
            email_notification=email_notification,
            created_by=created_by,
        )
        return True
    return False


def _send_sms_to_customer(customer, template_name, context, campaign_id, created_by):
    """Send SMS campaign to a single customer."""
    if not customer.phone:
        return False
    
    user = User.objects.filter(email=customer.email).first() if customer.email else None
    if not user:
        user = User.objects.filter(phone=customer.phone).first()
    if not user:
        return False
    
    sms_notification = send_marketing_sms(
        user=user,
        template_name=template_name,
        context={**context, "customer": customer},
        campaign_id=campaign_id,
    )
    
    if sms_notification:
        log_customer_communication(
            customer=customer,
            communication_type="SMS",
            direction="OUTBOUND",
            subject="Marketing SMS",
            content=f"Marketing SMS sent using template: {template_name}",
            campaign_id=campaign_id,
            sms_notification=sms_notification,
            created_by=created_by,
        )
        return True
    return False


def send_bulk_campaign_to_segment(
    segment_id: str,
    campaign_type: str,
    template_name: str,
    subject: str = "",
    context: Optional[Dict] = None,
    created_by: Optional[User] = None,
) -> Dict:
    """
    Send a bulk campaign to a customer segment.

    Args:
        segment_id: Customer segment ID
        campaign_type: Type of campaign (EMAIL or SMS)
        template_name: Template to use
        subject: Email subject (for email campaigns)
        context: Template context variables
        created_by: User creating the campaign

    Returns:
        Dictionary with campaign results
    """
    from .models import CustomerSegment

    try:
        segment = CustomerSegment.objects.get(id=segment_id)
        customers = segment.get_customers()

        campaign_id = str(uuid.uuid4())
        analytics = create_campaign_analytics(
            campaign_id=campaign_id,
            campaign_name=f"{segment.name} - {template_name}",
            campaign_type=campaign_type,
            segment=segment,
        )

        sent_count = 0
        failed_count = 0
        context = context or {}

        for customer in customers:
            try:
                success = False
                if campaign_type == "EMAIL":
                    success = _send_email_to_customer(
                        customer, template_name, context, campaign_id, subject, created_by
                    )
                elif campaign_type == "SMS":
                    success = _send_sms_to_customer(
                        customer, template_name, context, campaign_id, created_by
                    )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send {campaign_type} to customer {customer.id}: {str(e)}")
                failed_count += 1

        analytics.total_recipients = customers.count()
        analytics.messages_sent = sent_count
        analytics.messages_failed = failed_count
        analytics.save(update_fields=["total_recipients", "messages_sent", "messages_failed"])

        result = {
            "campaign_id": campaign_id,
            "segment_name": segment.name,
            "total_customers": customers.count(),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "success_rate": (
                round((sent_count / customers.count()) * 100, 2) if customers.count() > 0 else 0
            ),
        }

        logger.info(
            f"Bulk campaign sent to segment '{segment.name}': {sent_count} sent, {failed_count} failed"
        )
        return result

    except CustomerSegment.DoesNotExist:
        logger.error(f"Customer segment {segment_id} not found")
        return {"error": "Segment not found"}
