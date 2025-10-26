"""
Management command to create backup alert email and SMS templates.
"""

from django.core.management.base import BaseCommand

from apps.notifications.models import EmailTemplate, SMSTemplate


class Command(BaseCommand):
    """Create backup alert notification templates."""

    help = "Create email and SMS templates for backup alerts"

    def handle(self, *args, **options):
        """Create backup alert templates."""
        self.stdout.write("Creating backup alert templates...")

        # Create email templates
        email_templates = {
            "backup_alert": {
                "subject_template": "[{{ alert.severity }}] Backup Alert: {{ alert.alert_type }}",
                "html_template": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: {% if alert.severity == 'CRITICAL' %}#dc3545{% elif alert.severity == 'ERROR' %}#fd7e14{% elif alert.severity == 'WARNING' %}#ffc107{% else %}#17a2b8{% endif %}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }
        .content { background-color: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px; }
        .alert-details { background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid {% if alert.severity == 'CRITICAL' %}#dc3545{% elif alert.severity == 'ERROR' %}#fd7e14{% elif alert.severity == 'WARNING' %}#ffc107{% else %}#17a2b8{% endif %}; }
        .button { display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #6c757d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Backup Alert: {{ alert.alert_type }}</h2>
            <p>Severity: {{ alert.severity }}</p>
        </div>
        <div class="content">
            <div class="alert-details">
                <h3>Alert Message</h3>
                <p>{{ alert.message }}</p>

                <h4>Details</h4>
                <p><strong>Alert Type:</strong> {{ alert.alert_type }}</p>
                <p><strong>Severity:</strong> {{ alert.severity }}</p>
                <p><strong>Created:</strong> {{ alert.created_at }}</p>

                {% if alert.backup %}
                <h4>Backup Information</h4>
                <p><strong>Backup Type:</strong> {{ alert.backup.backup_type }}</p>
                <p><strong>Filename:</strong> {{ alert.backup.filename }}</p>
                <p><strong>Status:</strong> {{ alert.backup.status }}</p>
                {% endif %}

                {% if alert.details %}
                <h4>Additional Details</h4>
                <pre>{{ alert.details }}</pre>
                {% endif %}
            </div>

            <a href="{{ action_url }}" class="button">View Alert Details</a>
        </div>
        <div class="footer">
            <p>This is an automated alert from the Jewelry Shop Backup System</p>
            <p>Please do not reply to this email</p>
        </div>
    </div>
</body>
</html>
                """,
                "text_template": """
BACKUP ALERT: {{ alert.alert_type }}
Severity: {{ alert.severity }}

{{ alert.message }}

Details:
- Alert Type: {{ alert.alert_type }}
- Severity: {{ alert.severity }}
- Created: {{ alert.created_at }}

{% if alert.backup %}
Backup Information:
- Backup Type: {{ alert.backup.backup_type }}
- Filename: {{ alert.backup.filename }}
- Status: {{ alert.backup.status }}
{% endif %}

{% if alert.details %}
Additional Details:
{{ alert.details }}
{% endif %}

View alert details: {{ action_url }}

---
This is an automated alert from the Jewelry Shop Backup System
                """,
                "email_type": "SYSTEM",
            },
            "backup_alert_digest": {
                "subject_template": "Daily Backup Alert Digest: {{ total_active }} Active Alerts",
                "html_template": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #007bff; color: white; padding: 20px; border-radius: 5px 5px 0 0; }
        .content { background-color: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px; }
        .summary { background-color: white; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .alert-list { background-color: white; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .alert-item { padding: 10px; margin: 10px 0; border-left: 4px solid #dc3545; background-color: #f8f9fa; }
        .alert-item.warning { border-left-color: #ffc107; }
        .alert-item.error { border-left-color: #fd7e14; }
        .button { display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #6c757d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Daily Backup Alert Digest</h2>
            <p>{{ summary.active_alerts }} Active Alerts</p>
        </div>
        <div class="content">
            <div class="summary">
                <h3>Summary</h3>
                <p><strong>Total Alerts:</strong> {{ summary.total_alerts }}</p>
                <p><strong>Active Alerts:</strong> {{ summary.active_alerts }}</p>
                <p><strong>Critical Alerts:</strong> {{ summary.critical_alerts }}</p>
                <p><strong>Recent (24h):</strong> {{ summary.recent_alerts_24h }}</p>
            </div>

            {% if critical_alerts %}
            <div class="alert-list">
                <h3>Critical Alerts</h3>
                {% for alert in critical_alerts %}
                <div class="alert-item">
                    <strong>{{ alert.alert_type }}</strong><br>
                    {{ alert.message }}<br>
                    <small>{{ alert.created_at }}</small>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if error_alerts %}
            <div class="alert-list">
                <h3>Error Alerts</h3>
                {% for alert in error_alerts %}
                <div class="alert-item error">
                    <strong>{{ alert.alert_type }}</strong><br>
                    {{ alert.message }}<br>
                    <small>{{ alert.created_at }}</small>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% if warning_alerts %}
            <div class="alert-list">
                <h3>Warning Alerts</h3>
                {% for alert in warning_alerts %}
                <div class="alert-item warning">
                    <strong>{{ alert.alert_type }}</strong><br>
                    {{ alert.message }}<br>
                    <small>{{ alert.created_at }}</small>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <a href="/admin/backups/alerts/" class="button">View All Alerts</a>
        </div>
        <div class="footer">
            <p>This is an automated digest from the Jewelry Shop Backup System</p>
        </div>
    </div>
</body>
</html>
                """,
                "text_template": """
DAILY BACKUP ALERT DIGEST
{{ summary.active_alerts }} Active Alerts

SUMMARY:
- Total Alerts: {{ summary.total_alerts }}
- Active Alerts: {{ summary.active_alerts }}
- Critical Alerts: {{ summary.critical_alerts }}
- Recent (24h): {{ summary.recent_alerts_24h }}

{% if critical_alerts %}
CRITICAL ALERTS:
{% for alert in critical_alerts %}
- {{ alert.alert_type }}: {{ alert.message }}
  Created: {{ alert.created_at }}
{% endfor %}
{% endif %}

{% if error_alerts %}
ERROR ALERTS:
{% for alert in error_alerts %}
- {{ alert.alert_type }}: {{ alert.message }}
  Created: {{ alert.created_at }}
{% endfor %}
{% endif %}

{% if warning_alerts %}
WARNING ALERTS:
{% for alert in warning_alerts %}
- {{ alert.alert_type }}: {{ alert.message }}
  Created: {{ alert.created_at }}
{% endfor %}
{% endif %}

View all alerts: /admin/backups/alerts/

---
This is an automated digest from the Jewelry Shop Backup System
                """,
                "email_type": "SYSTEM",
            },
        }

        for name, template_data in email_templates.items():
            email_template, created = EmailTemplate.objects.update_or_create(
                name=name,
                defaults={
                    "subject_template": template_data["subject_template"],
                    "html_template": template_data["html_template"],
                    "text_template": template_data.get("text_template", ""),
                    "email_type": template_data["email_type"],
                    "is_active": True,
                },
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created email template: {name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated email template: {name}"))

        # Create SMS templates
        sms_templates = {
            "backup_alert_critical": {
                "message_template": "CRITICAL BACKUP ALERT: {{ alert.message[:100] }}. Check admin panel for details.",
                "sms_type": "ALERT",
            },
        }

        for name, template_data in sms_templates.items():
            sms_template, created = SMSTemplate.objects.update_or_create(
                name=name,
                defaults={
                    "message_template": template_data["message_template"],
                    "sms_type": template_data["sms_type"],
                    "is_active": True,
                },
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created SMS template: {name}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated SMS template: {name}"))

        self.stdout.write(self.style.SUCCESS("\nAll backup alert templates created successfully!"))
