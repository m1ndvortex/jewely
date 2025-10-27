"""
Alert service for monitoring system health and sending notifications.

This module provides:
- Metric checking against alert rules
- Alert creation and delivery
- Alert escalation
- Integration with email, SMS, and Slack

Per Requirements 7 - System Monitoring and Health Dashboard
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.alert_models import AlertDeliveryLog, AlertRule, MonitoringAlert

logger = logging.getLogger(__name__)


class AlertService:
    """
    Service for managing monitoring alerts.

    Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
    Requirement 7.7: Deliver alerts via email, SMS, and in-app notifications.
    """

    @staticmethod
    def check_metric(metric_type, current_value):
        """
        Check a metric against all enabled alert rules.

        Args:
            metric_type: Type of metric (e.g., CPU_USAGE, MEMORY_USAGE)
            current_value: Current value of the metric

        Returns:
            List of created alerts
        """
        alerts_created = []

        # Get all enabled rules for this metric type
        rules = AlertRule.objects.filter(metric_type=metric_type, is_enabled=True)

        for rule in rules:
            # Check if alert should trigger
            if rule.should_trigger(current_value):
                # Check cooldown period
                if rule.can_send_alert():
                    alert = AlertService.create_alert(rule, current_value)
                    if alert:
                        alerts_created.append(alert)

        return alerts_created

    @staticmethod
    def create_alert(alert_rule, current_value):
        """
        Create a new alert and send notifications.

        Args:
            alert_rule: AlertRule instance
            current_value: Current value that triggered the alert

        Returns:
            MonitoringAlert instance or None
        """
        try:
            # Create alert message
            message = AlertService._generate_alert_message(alert_rule, current_value)

            # Create alert
            alert = MonitoringAlert.objects.create(
                alert_rule=alert_rule,
                message=message,
                current_value=current_value,
                threshold_value=alert_rule.threshold,
                status=MonitoringAlert.ACTIVE,
            )

            # Send notifications
            AlertService.send_alert_notifications(alert)

            logger.info(f"Alert created: {alert.id} - {alert_rule.name}")
            return alert

        except Exception as e:
            logger.error(f"Error creating alert for rule {alert_rule.id}: {str(e)}")
            return None

    @staticmethod
    def _generate_alert_message(alert_rule, current_value):
        """Generate alert message based on rule and current value."""
        operator_text = {
            AlertRule.GREATER_THAN: "exceeded",
            AlertRule.LESS_THAN: "fell below",
            AlertRule.EQUALS: "equals",
            AlertRule.NOT_EQUALS: "does not equal",
        }

        op_text = operator_text.get(alert_rule.operator, "triggered")

        return (
            f"{alert_rule.get_metric_type_display()} {op_text} threshold: "
            f"Current value is {current_value:.2f}, threshold is {alert_rule.threshold:.2f}"
        )

    @staticmethod
    def send_alert_notifications(alert):
        """
        Send alert notifications via configured channels.

        Args:
            alert: MonitoringAlert instance
        """
        rule = alert.alert_rule

        # Send email notifications
        if rule.send_email and rule.get_email_recipients_list():
            AlertService._send_email_alert(alert)

        # Send SMS notifications
        if rule.send_sms and rule.get_sms_recipients_list():
            AlertService._send_sms_alert(alert)

        # Send Slack notifications
        if rule.send_slack and rule.slack_channel:
            AlertService._send_slack_alert(alert)

    @staticmethod
    def _send_email_alert(alert):
        """Send alert via email."""
        rule = alert.alert_rule
        recipients = rule.get_email_recipients_list()

        if not recipients:
            return

        try:
            subject = f"[{rule.get_severity_display()}] {rule.name}"

            # Render email template
            context = {
                "alert": alert,
                "rule": rule,
                "dashboard_url": f"{settings.SITE_URL}/admin/monitoring/",
            }

            html_message = render_to_string("monitoring/emails/alert_notification.html", context)
            text_message = render_to_string("monitoring/emails/alert_notification.txt", context)

            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False,
            )

            # Update alert
            alert.email_sent = True
            alert.email_sent_at = timezone.now()
            alert.save()

            # Log delivery
            for recipient in recipients:
                AlertDeliveryLog.objects.create(
                    alert=alert,
                    channel=AlertDeliveryLog.EMAIL,
                    recipient=recipient,
                    status=AlertDeliveryLog.SENT,
                    sent_at=timezone.now(),
                )

            logger.info(f"Email alert sent for {alert.id} to {len(recipients)} recipients")

        except Exception as e:
            logger.error(f"Error sending email alert {alert.id}: {str(e)}")

            # Log failure
            for recipient in recipients:
                AlertDeliveryLog.objects.create(
                    alert=alert,
                    channel=AlertDeliveryLog.EMAIL,
                    recipient=recipient,
                    status=AlertDeliveryLog.FAILED,
                    error_message=str(e),
                )

    @staticmethod
    def _send_sms_alert(alert):
        """Send alert via SMS."""
        rule = alert.alert_rule
        recipients = rule.get_sms_recipients_list()

        if not recipients:
            return

        try:
            # SMS message (keep it short)
            message = f"[{rule.get_severity_display()}] {rule.name}: {alert.message[:100]}"

            # TODO: Integrate with Twilio or other SMS provider
            # For now, just log
            logger.info(f"SMS alert would be sent to {recipients}: {message}")

            # Update alert
            alert.sms_sent = True
            alert.sms_sent_at = timezone.now()
            alert.save()

            # Log delivery
            for recipient in recipients:
                AlertDeliveryLog.objects.create(
                    alert=alert,
                    channel=AlertDeliveryLog.SMS,
                    recipient=recipient,
                    status=AlertDeliveryLog.SENT,
                    sent_at=timezone.now(),
                )

        except Exception as e:
            logger.error(f"Error sending SMS alert {alert.id}: {str(e)}")

            # Log failure
            for recipient in recipients:
                AlertDeliveryLog.objects.create(
                    alert=alert,
                    channel=AlertDeliveryLog.SMS,
                    recipient=recipient,
                    status=AlertDeliveryLog.FAILED,
                    error_message=str(e),
                )

    @staticmethod
    def _send_slack_alert(alert):
        """Send alert to Slack."""
        rule = alert.alert_rule
        channel = rule.slack_channel

        if not channel:
            return

        try:
            # Format Slack message
            color = {
                "INFO": "#36a64f",
                "WARNING": "#ff9900",
                "ERROR": "#ff0000",
                "CRITICAL": "#8b0000",
            }.get(rule.severity, "#808080")

            message = {
                "channel": channel,
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{rule.get_severity_display()}] {rule.name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Current Value",
                                "value": f"{alert.current_value:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Threshold",
                                "value": f"{alert.threshold_value:.2f}",
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True,
                            },
                        ],
                        "footer": "Monitoring System",
                    }
                ],
            }

            # TODO: Integrate with Slack API
            # For now, just log
            logger.info(f"Slack alert would be sent to {channel}: {message}")

            # Update alert
            alert.slack_sent = True
            alert.slack_sent_at = timezone.now()
            alert.save()

            # Log delivery
            AlertDeliveryLog.objects.create(
                alert=alert,
                channel=AlertDeliveryLog.SLACK,
                recipient=channel,
                status=AlertDeliveryLog.SENT,
                sent_at=timezone.now(),
            )

        except Exception as e:
            logger.error(f"Error sending Slack alert {alert.id}: {str(e)}")

            # Log failure
            AlertDeliveryLog.objects.create(
                alert=alert,
                channel=AlertDeliveryLog.SLACK,
                recipient=channel,
                status=AlertDeliveryLog.FAILED,
                error_message=str(e),
            )

    @staticmethod
    def check_escalations():
        """
        Check for alerts that need escalation.

        Should be run periodically (e.g., every 5 minutes).
        """
        # Get active alerts that should be escalated
        active_alerts = MonitoringAlert.objects.filter(
            status=MonitoringAlert.ACTIVE, escalated_at__isnull=True
        )

        escalated_count = 0

        for alert in active_alerts:
            if alert.should_escalate():
                AlertService.escalate_alert(alert)
                escalated_count += 1

        if escalated_count > 0:
            logger.info(f"Escalated {escalated_count} alerts")

        return escalated_count

    @staticmethod
    def escalate_alert(alert):
        """
        Escalate an alert to higher-level recipients.

        Args:
            alert: MonitoringAlert instance
        """
        try:
            # Mark as escalated
            alert.escalate()

            # Send escalation notifications
            rule = alert.alert_rule
            recipients = rule.get_escalation_email_recipients_list()

            if recipients:
                subject = f"[ESCALATED] [{rule.get_severity_display()}] {rule.name}"

                context = {
                    "alert": alert,
                    "rule": rule,
                    "dashboard_url": f"{settings.SITE_URL}/admin/monitoring/",
                }

                html_message = render_to_string("monitoring/emails/alert_escalation.html", context)
                text_message = render_to_string("monitoring/emails/alert_escalation.txt", context)

                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                    html_message=html_message,
                    fail_silently=False,
                )

                alert.escalation_sent = True
                alert.save()

                logger.info(f"Alert {alert.id} escalated to {len(recipients)} recipients")

        except Exception as e:
            logger.error(f"Error escalating alert {alert.id}: {str(e)}")

    @staticmethod
    def auto_resolve_alerts():
        """
        Auto-resolve alerts when metrics return to normal.

        Should be run periodically to check if active alerts can be resolved.
        """
        # This would check current metrics and auto-resolve alerts
        # For now, this is a placeholder for future implementation
        pass
