"""
Celery tasks for email notifications.
"""

import logging
from typing import Dict, List, Optional

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import EmailCampaign, EmailNotification
from .services import _send_email_now, process_scheduled_emails, send_campaign

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_email_task(self, email_notification_id: str):
    """
    Celery task to send an individual email.

    Args:
        email_notification_id: UUID of the EmailNotification to send
    """
    try:
        email_notification = EmailNotification.objects.get(id=email_notification_id)

        if email_notification.status != "PENDING":
            logger.warning(
                f"Email {email_notification_id} is not pending (status: {email_notification.status})"
            )
            return

        # Get template and render
        from .models import EmailTemplate

        template = EmailTemplate.objects.get(name=email_notification.template_name, is_active=True)

        # For now, we'll use basic context - in production, context should be stored or reconstructed
        context = {
            "user": email_notification.user,
            "timestamp": timezone.now(),
        }

        rendered = template.render(context)

        # Send email
        _send_email_now(email_notification, rendered["html_body"], rendered.get("text_body"))

        logger.info(f"Successfully sent email {email_notification_id}")

    except EmailNotification.DoesNotExist:
        logger.error(f"EmailNotification {email_notification_id} not found")

    except Exception as exc:
        logger.error(f"Failed to send email {email_notification_id}: {str(exc)}")

        # Update email status
        try:
            email_notification = EmailNotification.objects.get(id=email_notification_id)
            email_notification.update_status("FAILED", error_message=str(exc))
        except EmailNotification.DoesNotExist:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def send_bulk_email_task(
    user_ids: List[int],
    template_name: str,
    context: Dict,
    email_type: str = "MARKETING",
    campaign_id: Optional[str] = None,
):
    """
    Celery task to send bulk emails.

    Args:
        user_ids: List of user IDs to send emails to
        template_name: Name of the email template
        context: Context variables for template rendering
        email_type: Type of email
        campaign_id: Optional campaign ID for tracking
    """
    try:
        users = User.objects.filter(id__in=user_ids, email__isnull=False).exclude(email="")

        from .services import send_email_notification

        sent_count = 0
        failed_count = 0

        for user in users:
            try:
                email_notification = send_email_notification(
                    user=user,
                    template_name=template_name,
                    context=context,
                    email_type=email_type,
                    campaign_id=campaign_id,
                    create_in_app_notification=(email_type != "MARKETING"),
                )

                if email_notification:
                    sent_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Failed to send bulk email to user {user.id}: {str(e)}")
                failed_count += 1

        logger.info(f"Bulk email task completed: {sent_count} sent, {failed_count} failed")

        return {"sent": sent_count, "failed": failed_count, "total": len(user_ids)}

    except Exception as exc:
        logger.error(f"Bulk email task failed: {str(exc)}")
        raise


@shared_task
def send_campaign_task(campaign_id: str, context: Optional[Dict] = None):
    """
    Celery task to send an email campaign.

    Args:
        campaign_id: ID of the EmailCampaign to send
        context: Optional context variables for template rendering
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)

        if campaign.status not in ["DRAFT", "SCHEDULED"]:
            logger.warning(f"Campaign {campaign_id} cannot be sent (status: {campaign.status})")
            return

        sent_count = send_campaign(campaign, context)

        logger.info(f"Campaign {campaign_id} sent to {sent_count} users")

        return {"campaign_id": campaign_id, "sent_count": sent_count, "status": "completed"}

    except EmailCampaign.DoesNotExist:
        logger.error(f"EmailCampaign {campaign_id} not found")

    except Exception as exc:
        logger.error(f"Failed to send campaign {campaign_id}: {str(exc)}")

        # Update campaign status
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
            campaign.status = "CANCELLED"
            campaign.save()
        except EmailCampaign.DoesNotExist:
            pass

        raise


@shared_task
def process_scheduled_emails_task():
    """
    Celery task to process scheduled emails.
    This should be run periodically (e.g., every 5 minutes).
    """
    try:
        processed_count = process_scheduled_emails()

        logger.info(f"Processed {processed_count} scheduled emails")

        return {"processed_count": processed_count, "timestamp": timezone.now().isoformat()}

    except Exception as exc:
        logger.error(f"Failed to process scheduled emails: {str(exc)}")
        raise


@shared_task
def cleanup_old_email_notifications_task(days: int = 90):
    """
    Celery task to clean up old email notifications.

    Args:
        days: Number of days to keep email notifications (default: 90)
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        # Delete old email notifications (except failed ones which we keep longer)
        deleted_count, _ = (
            EmailNotification.objects.filter(created_at__lt=cutoff_date)
            .exclude(status="FAILED")
            .delete()
        )

        logger.info(f"Cleaned up {deleted_count} old email notifications")

        return {"deleted_count": deleted_count, "cutoff_date": cutoff_date.isoformat()}

    except Exception as exc:
        logger.error(f"Failed to cleanup old email notifications: {str(exc)}")
        raise


@shared_task
def update_campaign_statistics_task(campaign_id: str):
    """
    Celery task to update campaign statistics.

    Args:
        campaign_id: ID of the EmailCampaign to update statistics for
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
        campaign.update_statistics()

        logger.info(f"Updated statistics for campaign {campaign_id}")

        return {
            "campaign_id": campaign_id,
            "total_recipients": campaign.total_recipients,
            "emails_sent": campaign.emails_sent,
            "emails_delivered": campaign.emails_delivered,
            "emails_opened": campaign.emails_opened,
            "emails_clicked": campaign.emails_clicked,
        }

    except EmailCampaign.DoesNotExist:
        logger.error(f"EmailCampaign {campaign_id} not found")

    except Exception as exc:
        logger.error(f"Failed to update campaign statistics for {campaign_id}: {str(exc)}")
        raise


@shared_task
def send_transactional_email_task(
    user_id: int, template_name: str, context: Dict, subject: Optional[str] = None
):
    """
    Celery task to send a transactional email.

    Args:
        user_id: ID of the user to send email to
        template_name: Name of the email template
        context: Context variables for template rendering
        subject: Optional override for email subject
    """
    try:
        user = User.objects.get(id=user_id)

        from .services import send_transactional_email

        email_notification = send_transactional_email(
            user=user, template_name=template_name, context=context, subject=subject
        )

        if email_notification:
            logger.info(f"Sent transactional email '{template_name}' to user {user_id}")
            return {"email_notification_id": str(email_notification.id), "status": "sent"}
        else:
            logger.warning(
                f"Failed to send transactional email '{template_name}' to user {user_id}"
            )
            return {"status": "failed", "reason": "Email notification not created"}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")

    except Exception as exc:
        logger.error(f"Failed to send transactional email to user {user_id}: {str(exc)}")
        raise


@shared_task
def generate_email_report_task(start_date: str, end_date: str, email_type: Optional[str] = None):
    """
    Celery task to generate email statistics report.

    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
        email_type: Optional email type filter
    """
    try:
        from django.utils.dateparse import parse_datetime

        start_dt = parse_datetime(start_date)
        end_dt = parse_datetime(end_date)

        queryset = EmailNotification.objects.filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        )

        if email_type:
            queryset = queryset.filter(email_type=email_type)

        # Generate statistics
        stats = {
            "period": {"start": start_date, "end": end_date, "email_type": email_type},
            "total_emails": queryset.count(),
            "by_status": {},
            "by_type": {},
            "by_day": {},
        }

        # Statistics by status
        for status_choice in EmailNotification.STATUS_CHOICES:
            status = status_choice[0]
            count = queryset.filter(status=status).count()
            stats["by_status"][status] = count

        # Statistics by type
        for type_choice in EmailNotification.EMAIL_TYPES:
            email_type_val = type_choice[0]
            count = queryset.filter(email_type=email_type_val).count()
            stats["by_type"][email_type_val] = count

        # Daily statistics
        from django.db.models import Count
        from django.db.models.functions import TruncDate

        daily_stats = (
            queryset.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        for day_stat in daily_stats:
            stats["by_day"][day_stat["date"].isoformat()] = day_stat["count"]

        logger.info(f"Generated email report for period {start_date} to {end_date}")

        return stats

    except Exception as exc:
        logger.error(f"Failed to generate email report: {str(exc)}")
        raise
