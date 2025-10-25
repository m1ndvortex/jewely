"""
Management command to create default SMS templates.
"""

from django.core.management.base import BaseCommand

from apps.notifications.models import SMSTemplate


class Command(BaseCommand):
    help = "Create default SMS templates for common notifications"

    def handle(self, *args, **options):
        """Create default SMS templates"""

        templates = [
            # Order Status Templates
            {
                "name": "order_confirmed",
                "message_template": "Hi {{ user.first_name }}, your order #{{ order_number }} has been confirmed. Total: ${{ total_amount }}. We'll notify you when it's ready for pickup.",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "order_ready",
                "message_template": "Great news {{ user.first_name }}! Your order #{{ order_number }} is ready for pickup at {{ branch_name }}. Please bring your receipt.",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "repair_status_update",
                "message_template": "Update on your repair order #{{ order_number }}: {{ status_message }}. Estimated completion: {{ estimated_date }}. Questions? Call {{ branch_phone }}.",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "custom_order_update",
                "message_template": "Your custom jewelry order #{{ order_number }} status: {{ status }}. {{ message }}. Contact us at {{ branch_phone }} for details.",
                "sms_type": "TRANSACTIONAL",
            },
            # Appointment Templates
            {
                "name": "appointment_reminder",
                "message_template": "Reminder: You have an appointment tomorrow at {{ appointment_time }} at {{ branch_name }}. Address: {{ branch_address }}. Call {{ branch_phone }} to reschedule.",
                "sms_type": "ALERT",
            },
            {
                "name": "appointment_confirmed",
                "message_template": "Your appointment is confirmed for {{ appointment_date }} at {{ appointment_time }} at {{ branch_name }}. We look forward to seeing you!",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "appointment_cancelled",
                "message_template": "Your appointment on {{ appointment_date }} has been cancelled. Please call {{ branch_phone }} to reschedule. We apologize for any inconvenience.",
                "sms_type": "TRANSACTIONAL",
            },
            # Payment Reminder Templates
            {
                "name": "payment_reminder",
                "message_template": "Payment reminder: Your invoice #{{ invoice_number }} for ${{ amount }} is due on {{ due_date }}. Pay online or visit our store. Questions? Call {{ branch_phone }}.",
                "sms_type": "ALERT",
            },
            {
                "name": "payment_overdue",
                "message_template": "Your payment of ${{ amount }} for invoice #{{ invoice_number }} is overdue. Please contact us at {{ branch_phone }} to arrange payment.",
                "sms_type": "ALERT",
            },
            {
                "name": "payment_received",
                "message_template": "Thank you! We've received your payment of ${{ amount }} for invoice #{{ invoice_number }}. Your account is now up to date.",
                "sms_type": "TRANSACTIONAL",
            },
            # Inventory & Stock Alerts
            {
                "name": "low_stock_alert",
                "message_template": "ALERT: {{ item_name }} is running low ({{ current_stock }} remaining). Consider restocking soon to avoid stockouts.",
                "sms_type": "ALERT",
            },
            {
                "name": "out_of_stock_alert",
                "message_template": "URGENT: {{ item_name }} is out of stock at {{ branch_name }}. Immediate restocking required.",
                "sms_type": "ALERT",
            },
            {
                "name": "restock_notification",
                "message_template": "Good news! {{ item_name }} is back in stock at {{ branch_name }}. Visit us or call {{ branch_phone }} to reserve yours.",
                "sms_type": "TRANSACTIONAL",
            },
            # Loyalty & Marketing Templates
            {
                "name": "loyalty_points_earned",
                "message_template": "You earned {{ points }} loyalty points! Your balance: {{ total_points }} points. Redeem for rewards at {{ branch_name }}.",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "loyalty_tier_upgrade",
                "message_template": "Congratulations {{ user.first_name }}! You've been upgraded to {{ new_tier }} status. Enjoy {{ discount }}% discount on all purchases!",
                "sms_type": "TRANSACTIONAL",
            },
            {
                "name": "special_promotion",
                "message_template": "Special offer for you! {{ promotion_title }}: {{ discount_text }}. Valid until {{ expiry_date }}. Show this SMS in-store. Reply STOP to opt out.",
                "sms_type": "MARKETING",
            },
            {
                "name": "birthday_offer",
                "message_template": "Happy Birthday {{ user.first_name }}! 🎉 Enjoy {{ discount }}% off your next purchase. Valid for 30 days. Visit {{ branch_name }} to celebrate!",
                "sms_type": "MARKETING",
            },
            # Security & System Templates
            {
                "name": "security_alert",
                "message_template": "Security Alert: {{ alert_message }} If this wasn't you, please contact us immediately at {{ support_phone }}.",
                "sms_type": "SYSTEM",
            },
            {
                "name": "password_reset",
                "message_template": "Your password reset code is: {{ reset_code }}. This code expires in 15 minutes. Don't share this code with anyone.",
                "sms_type": "SYSTEM",
            },
            {
                "name": "account_locked",
                "message_template": "Your account has been temporarily locked due to multiple failed login attempts. Contact {{ support_phone }} for assistance.",
                "sms_type": "SYSTEM",
            },
            # General Business Templates
            {
                "name": "store_hours_change",
                "message_template": "Notice: {{ branch_name }} hours have changed. New hours: {{ new_hours }}. Effective {{ effective_date }}. Questions? Call {{ branch_phone }}.",
                "sms_type": "SYSTEM",
            },
            {
                "name": "holiday_closure",
                "message_template": "{{ branch_name }} will be closed on {{ holiday_date }} for {{ holiday_name }}. We'll reopen on {{ reopen_date }}. Happy {{ holiday_name }}!",
                "sms_type": "SYSTEM",
            },
            {
                "name": "maintenance_notice",
                "message_template": "Scheduled maintenance: Our systems will be unavailable from {{ start_time }} to {{ end_time }} on {{ date }}. We apologize for any inconvenience.",
                "sms_type": "SYSTEM",
            },
        ]

        created_count = 0
        updated_count = 0

        for template_data in templates:
            template, created = SMSTemplate.objects.update_or_create(
                name=template_data["name"],
                defaults={
                    "message_template": template_data["message_template"],
                    "sms_type": template_data["sms_type"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created SMS template: {template.name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"Updated SMS template: {template.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSMS template creation completed!"
                f"\nCreated: {created_count} templates"
                f"\nUpdated: {updated_count} templates"
                f"\nTotal: {len(templates)} templates processed"
            )
        )
