"""
Services for repair order management.

This module contains business logic and services for repair orders,
including notification handling and status updates.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def send_repair_status_notification(repair_order):
    """
    Send notification to customer about repair order status change.

    This is a placeholder implementation that will be enhanced
    when the full notification system is implemented in task 13.

    Args:
        repair_order: RepairOrder instance
    """
    try:
        # Get customer email
        if not repair_order.customer.email:
            return False

        # Prepare email content based on status
        status_messages = {
            "received": "Your repair order has been received and is being reviewed.",
            "in_progress": "Work has started on your repair order.",
            "quality_check": "Your repair is undergoing quality inspection.",
            "completed": "Your repair has been completed and is ready for pickup.",
            "delivered": "Your repair order has been delivered. Thank you for your business!",
            "cancelled": "Your repair order has been cancelled. Please contact us for more information.",
        }

        subject = f"Repair Order Update - {repair_order.order_number}"
        message = status_messages.get(
            repair_order.status, "Your repair order status has been updated."
        )

        # Email context for future template rendering
        # context = {
        #     "repair_order": repair_order,
        #     "customer": repair_order.customer,
        #     "status_message": message,
        #     "shop_name": repair_order.tenant.company_name,
        # }

        # Render email template (placeholder - will be enhanced later)
        email_body = f"""
Dear {repair_order.customer.first_name},

{message}

Order Details:
- Order Number: {repair_order.order_number}
- Item: {repair_order.item_description}
- Service: {repair_order.get_service_type_display()}
- Status: {repair_order.get_status_display()}

Thank you for choosing {repair_order.tenant.company_name}.

Best regards,
{repair_order.tenant.company_name} Team
        """

        # Send email (if email backend is configured)
        if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[repair_order.customer.email],
                fail_silently=True,  # Don't break the flow if email fails
            )

        return True

    except Exception as e:
        # Log the error (in a real implementation, use proper logging)
        print(f"Failed to send notification for repair order {repair_order.order_number}: {e}")
        return False


def send_work_order_notification(repair_orders, craftsman, notes=None):
    """
    Send notification to craftsman about new work order assignment.

    Args:
        repair_orders: QuerySet of RepairOrder instances
        craftsman: User instance (craftsman)
        notes: Optional notes for the craftsman
    """
    try:
        if not craftsman.email:
            return False

        subject = f'New Work Order Assignment - {timezone.now().strftime("%Y-%m-%d")}'

        # Create email body
        order_list = "\n".join(
            [
                f"- {order.order_number}: {order.item_description} ({order.get_service_type_display()})"
                for order in repair_orders
            ]
        )

        email_body = f"""
Dear {craftsman.get_full_name()},

You have been assigned new repair orders:

{order_list}

{f"Special Instructions: {notes}" if notes else ""}

Please review the work order details and begin work as scheduled.

Best regards,
Management Team
        """

        # Send email (if email backend is configured)
        if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[craftsman.email],
                fail_silently=True,
            )

        return True

    except Exception as e:
        print(f"Failed to send work order notification to {craftsman.get_full_name()}: {e}")
        return False
