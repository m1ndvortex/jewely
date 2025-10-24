"""
Management command to create default email templates.
"""

from django.core.management.base import BaseCommand
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from apps.notifications.models import EmailTemplate


class Command(BaseCommand):
    help = "Create default email templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing templates",
        )

    def handle(self, *args, **options):
        templates = [
            # Transactional emails
            {
                "name": "order_confirmation",
                "subject_template": "Order Confirmation - {{ order.order_number }}",
                "html_template": "emails/transactional/order_confirmation.html",
                "email_type": "TRANSACTIONAL",
            },
            {
                "name": "receipt",
                "subject_template": "Receipt - {{ sale.sale_number }}",
                "html_template": "emails/transactional/receipt.html",
                "email_type": "TRANSACTIONAL",
            },
            {
                "name": "password_reset",
                "subject_template": "Password Reset Request",
                "html_template": "emails/transactional/password_reset.html",
                "email_type": "TRANSACTIONAL",
            },
            {
                "name": "low_stock_alert",
                "subject_template": 'Low Stock Alert - {{ branch.name|default:"Multiple Branches" }}',
                "html_template": "emails/transactional/low_stock_alert.html",
                "email_type": "TRANSACTIONAL",
            },
            # Marketing emails
            {
                "name": "promotional_campaign",
                "subject_template": "{{ campaign_title }} - Special Offer Inside!",
                "html_template": "emails/marketing/promotional_campaign.html",
                "email_type": "MARKETING",
            },
            {
                "name": "loyalty_program",
                "subject_template": "Your Loyalty Status - {{ customer.loyalty_points }} Points Available!",
                "html_template": "emails/marketing/loyalty_program.html",
                "email_type": "MARKETING",
            },
            # System emails
            {
                "name": "maintenance_notification",
                "subject_template": 'Scheduled System Maintenance - {{ maintenance_start|date:"M d, Y" }}',
                "html_template": "emails/system/maintenance_notification.html",
                "email_type": "SYSTEM",
            },
            {
                "name": "security_alert",
                "subject_template": "Security Alert - {{ alert_type }}",
                "html_template": "emails/system/security_alert.html",
                "email_type": "SYSTEM",
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for template_data in templates:
            name = template_data["name"]

            # Check if template file exists
            try:
                get_template(template_data["html_template"])
            except TemplateDoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'Template file {template_data["html_template"]} not found, skipping {name}'
                    )
                )
                skipped_count += 1
                continue

            # Check if email template already exists
            existing_template = EmailTemplate.objects.filter(name=name).first()

            if existing_template:
                if options["overwrite"]:
                    # Update existing template
                    existing_template.subject_template = template_data["subject_template"]
                    existing_template.html_template = self._load_template_content(
                        template_data["html_template"]
                    )
                    existing_template.email_type = template_data["email_type"]
                    existing_template.is_active = True
                    existing_template.save()

                    self.stdout.write(self.style.SUCCESS(f"Updated email template: {name}"))
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Email template {name} already exists, skipping (use --overwrite to update)"
                        )
                    )
                    skipped_count += 1
            else:
                # Create new template
                EmailTemplate.objects.create(
                    name=name,
                    subject_template=template_data["subject_template"],
                    html_template=self._load_template_content(template_data["html_template"]),
                    email_type=template_data["email_type"],
                    is_active=True,
                )

                self.stdout.write(self.style.SUCCESS(f"Created email template: {name}"))
                created_count += 1

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nEmail template creation complete:\n"
                f"  Created: {created_count}\n"
                f"  Updated: {updated_count}\n"
                f"  Skipped: {skipped_count}\n"
                f"  Total: {len(templates)}"
            )
        )

    def _load_template_content(self, template_path):
        """Load template content from file"""
        try:
            get_template(template_path)  # Just check if template exists
            # For now, we'll store the template path instead of content
            # This allows for dynamic template loading
            return f'{{% include "{template_path}" %}}'
        except TemplateDoesNotExist:
            return f"Template {template_path} not found"
