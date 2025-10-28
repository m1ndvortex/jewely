"""
Communication service for sending messages via multiple channels.

This module handles:
- Bulk email sending to multiple tenants
- SMS delivery
- In-app notification creation
- Communication logging

Per Requirement 31 - Communication and Announcement System
"""

import logging
from typing import Dict, List

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.core.announcement_models import CommunicationLog, DirectMessage
from apps.core.models import Tenant

logger = logging.getLogger(__name__)


class CommunicationService:
    """
    Service for handling multi-channel communication delivery.

    Requirement 31.8: Send direct messages to specific tenants.
    Requirement 31.10: Log all platform-to-tenant communications.
    """

    @staticmethod
    def send_direct_message(message: DirectMessage, created_by=None) -> Dict[str, bool]:
        """
        Send a direct message via selected channels.

        Args:
            message: DirectMessage instance to send
            created_by: User who initiated the send

        Returns:
            Dictionary with delivery status for each channel
        """
        delivery_status = {
            "email": False,
            "sms": False,
            "in_app": False,
        }

        channels = message.channels or []

        # Send via email
        if "email" in channels:
            delivery_status["email"] = CommunicationService._send_email(
                tenant=message.tenant,
                subject=message.subject,
                message=message.message,
            )
            message.email_sent = delivery_status["email"]

        # Send via SMS
        if "sms" in channels:
            delivery_status["sms"] = CommunicationService._send_sms(
                tenant=message.tenant,
                message=message.message,
            )
            message.sms_sent = delivery_status["sms"]

        # Create in-app notification
        if "in_app" in channels:
            delivery_status["in_app"] = CommunicationService._create_in_app_notification(
                tenant=message.tenant,
                subject=message.subject,
                message=message.message,
            )
            message.in_app_sent = delivery_status["in_app"]

        # Update message status
        if any(delivery_status.values()):
            message.mark_as_sent()
        else:
            message.status = DirectMessage.FAILED
            message.save()

        # Log the communication
        CommunicationService._log_communication(
            communication_type=CommunicationLog.DIRECT_MESSAGE,
            tenant=message.tenant,
            subject=message.subject,
            message=message.message,
            channels_used=channels,
            delivery_status=delivery_status,
            sent_by=created_by or message.created_by,
            direct_message=message,
        )

        return delivery_status

    @staticmethod
    def send_bulk_email(
        tenants: List[Tenant],
        subject: str,
        message: str,
        created_by=None,
    ) -> Dict[str, int]:
        """
        Send bulk email to multiple tenants.

        Requirement 31.8: Send direct messages to specific tenants.

        Args:
            tenants: List of Tenant objects to send to
            subject: Email subject
            message: Email message content
            created_by: User who initiated the send

        Returns:
            Dictionary with success and failure counts
        """
        results = {
            "success": 0,
            "failed": 0,
            "total": len(tenants),
        }

        for tenant in tenants:
            # Create a direct message record for each tenant
            direct_message = DirectMessage.objects.create(
                tenant=tenant,
                subject=subject,
                message=message,
                channels=["email"],
                created_by=created_by,
            )

            # Send the email
            success = CommunicationService._send_email(
                tenant=tenant,
                subject=subject,
                message=message,
            )

            if success:
                results["success"] += 1
                direct_message.email_sent = True
                direct_message.mark_as_sent()
            else:
                results["failed"] += 1
                direct_message.status = DirectMessage.FAILED
                direct_message.save()

            # Log the communication
            CommunicationService._log_communication(
                communication_type=CommunicationLog.DIRECT_MESSAGE,
                tenant=tenant,
                subject=subject,
                message=message,
                channels_used=["email"],
                delivery_status={"email": success},
                sent_by=created_by,
                direct_message=direct_message,
            )

        logger.info(
            f"Bulk email sent to {results['total']} tenants. "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    @staticmethod
    def _send_email(tenant: Tenant, subject: str, message: str) -> bool:
        """
        Send email to tenant's primary contact.

        Args:
            tenant: Tenant to send to
            subject: Email subject
            message: Email message

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get tenant owner's email
            tenant_owner = tenant.users.filter(role="TENANT_OWNER").first()

            if not tenant_owner or not tenant_owner.email:
                logger.warning(f"No email found for tenant {tenant.company_name}")
                return False

            # Render email template
            html_message = render_to_string(
                "core/emails/direct_message.html",
                {
                    "tenant": tenant,
                    "subject": subject,
                    "message": message,
                },
            )
            plain_message = strip_tags(html_message)

            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[tenant_owner.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Email sent to {tenant.company_name} ({tenant_owner.email})")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {tenant.company_name}: {str(e)}")
            return False

    @staticmethod
    def _send_sms(tenant: Tenant, message: str) -> bool:
        """
        Send SMS to tenant's primary contact.

        Args:
            tenant: Tenant to send to
            message: SMS message

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get tenant owner's phone
            tenant_owner = tenant.users.filter(role="TENANT_OWNER").first()

            if not tenant_owner or not tenant_owner.phone:
                logger.warning(f"No phone found for tenant {tenant.company_name}")
                return False

            # TODO: Integrate with SMS provider (Twilio, etc.)
            # For now, just log the SMS
            logger.info(
                f"SMS would be sent to {tenant.company_name} ({tenant_owner.phone}): {message[:50]}..."
            )

            # In production, this would be:
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=tenant_owner.phone
            # )

            return True

        except Exception as e:
            logger.error(f"Failed to send SMS to {tenant.company_name}: {str(e)}")
            return False

    @staticmethod
    def _create_in_app_notification(tenant: Tenant, subject: str, message: str) -> bool:
        """
        Create in-app notification for tenant.

        Args:
            tenant: Tenant to notify
            subject: Notification subject
            message: Notification message

        Returns:
            True if created successfully, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from apps.notifications.models import Notification

            # Get all tenant users
            tenant_users = tenant.users.all()

            for user in tenant_users:
                Notification.objects.create(
                    user=user,
                    title=subject,
                    message=message,
                    notification_type="SYSTEM",  # Use SYSTEM type which exists in the model
                    is_read=False,
                )

            logger.info(
                f"In-app notifications created for {tenant.company_name} ({tenant_users.count()} users)"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to create in-app notification for {tenant.company_name}: {str(e)}"
            )
            return False

    @staticmethod
    def _log_communication(
        communication_type: str,
        tenant: Tenant,
        subject: str,
        message: str,
        channels_used: List[str],
        delivery_status: Dict[str, bool],
        sent_by=None,
        announcement=None,
        direct_message=None,
    ):
        """
        Log communication to CommunicationLog.

        Requirement 31.10: Log all platform-to-tenant communications.

        Args:
            communication_type: Type of communication
            tenant: Tenant who received the communication
            subject: Subject/title
            message: Message content
            channels_used: List of channels used
            delivery_status: Status for each channel
            sent_by: User who sent the communication
            announcement: Related Announcement (if any)
            direct_message: Related DirectMessage (if any)
        """
        try:
            CommunicationLog.objects.create(
                communication_type=communication_type,
                tenant=tenant,
                subject=subject,
                message_preview=message[:500],  # Store first 500 chars
                channels_used=channels_used,
                delivery_status=delivery_status,
                sent_by=sent_by,
                announcement=announcement,
                direct_message=direct_message,
            )

            logger.info(f"Communication logged for {tenant.company_name}: {subject}")

        except Exception as e:
            logger.error(f"Failed to log communication: {str(e)}")


class BulkCommunicationService:
    """
    Service for handling bulk communications to multiple tenants.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    @staticmethod
    def send_bulk_message(
        tenant_ids: List[str],
        subject: str,
        message: str,
        channels: List[str],
        created_by=None,
    ) -> Dict[str, int]:
        """
        Send bulk message to multiple tenants via selected channels.

        Args:
            tenant_ids: List of tenant IDs to send to
            subject: Message subject
            message: Message content
            channels: List of channels to use
            created_by: User who initiated the send

        Returns:
            Dictionary with delivery statistics
        """
        tenants = Tenant.objects.filter(id__in=tenant_ids, status=Tenant.ACTIVE)

        results = {
            "total": tenants.count(),
            "success": 0,
            "failed": 0,
            "email_sent": 0,
            "sms_sent": 0,
            "in_app_sent": 0,
        }

        for tenant in tenants:
            # Create direct message record
            direct_message = DirectMessage.objects.create(
                tenant=tenant,
                subject=subject,
                message=message,
                channels=channels,
                created_by=created_by,
            )

            # Send via selected channels
            delivery_status = CommunicationService.send_direct_message(
                message=direct_message,
                created_by=created_by,
            )

            # Update statistics
            if any(delivery_status.values()):
                results["success"] += 1
            else:
                results["failed"] += 1

            if delivery_status.get("email"):
                results["email_sent"] += 1
            if delivery_status.get("sms"):
                results["sms_sent"] += 1
            if delivery_status.get("in_app"):
                results["in_app_sent"] += 1

        logger.info(
            f"Bulk message sent to {results['total']} tenants. "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    @staticmethod
    def send_to_plan(
        plan_name: str,
        subject: str,
        message: str,
        channels: List[str],
        created_by=None,
    ) -> Dict[str, int]:
        """
        Send message to all tenants on a specific subscription plan.

        Args:
            plan_name: Name of the subscription plan
            subject: Message subject
            message: Message content
            channels: List of channels to use
            created_by: User who initiated the send

        Returns:
            Dictionary with delivery statistics
        """
        # Get all tenants on the specified plan
        tenants = Tenant.objects.filter(
            subscription__plan__name=plan_name,
            status=Tenant.ACTIVE,
        )

        tenant_ids = list(tenants.values_list("id", flat=True))

        return BulkCommunicationService.send_bulk_message(
            tenant_ids=tenant_ids,
            subject=subject,
            message=message,
            channels=channels,
            created_by=created_by,
        )

    @staticmethod
    def send_to_all_active(
        subject: str,
        message: str,
        channels: List[str],
        created_by=None,
    ) -> Dict[str, int]:
        """
        Send message to all active tenants.

        Args:
            subject: Message subject
            message: Message content
            channels: List of channels to use
            created_by: User who initiated the send

        Returns:
            Dictionary with delivery statistics
        """
        tenants = Tenant.objects.filter(status=Tenant.ACTIVE)
        tenant_ids = list(tenants.values_list("id", flat=True))

        return BulkCommunicationService.send_bulk_message(
            tenant_ids=tenant_ids,
            subject=subject,
            message=message,
            channels=channels,
            created_by=created_by,
        )
