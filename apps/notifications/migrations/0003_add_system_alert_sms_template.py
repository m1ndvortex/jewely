# Generated migration for adding system alert SMS template

from django.db import migrations


def create_system_alert_template(apps, schema_editor):
    """Create SMS template for system alerts from Alertmanager"""
    SMSTemplate = apps.get_model('notifications', 'SMSTemplate')
    
    # Create system alert template if it doesn't exist
    SMSTemplate.objects.get_or_create(
        name='system_alert',
        defaults={
            'message_template': (
                '🚨 CRITICAL ALERT\n'
                '{{ alertname }}\n'
                'Service: {{ service }}\n'
                'Instance: {{ instance }}\n'
                '{{ summary }}'
            ),
            'sms_type': 'ALERT',
            'is_active': True,
        }
    )


def reverse_create_system_alert_template(apps, schema_editor):
    """Remove system alert SMS template"""
    SMSTemplate = apps.get_model('notifications', 'SMSTemplate')
    SMSTemplate.objects.filter(name='system_alert').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_auto_20241113_0000'),  # Update this to your latest migration
    ]

    operations = [
        migrations.RunPython(
            create_system_alert_template,
            reverse_create_system_alert_template
        ),
    ]
