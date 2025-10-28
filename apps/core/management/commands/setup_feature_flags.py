"""
Management command to set up initial feature flags.
Per Requirement 30 - Feature Flag Management
"""

from django.core.management.base import BaseCommand

from waffle.models import Flag, Sample, Switch


class Command(BaseCommand):
    help = "Set up initial feature flags for the platform"

    def handle(self, *args, **options):
        self.stdout.write("Setting up feature flags...")

        # Create Flags (user/group/tenant-specific features)
        flags = [
            {
                "name": "new_pos_interface",
                "note": "Enable new POS interface with enhanced features",
                "everyone": None,  # Not enabled for everyone by default
            },
            {
                "name": "advanced_reporting",
                "note": "Enable advanced reporting features with custom dashboards",
                "everyone": None,
            },
            {
                "name": "loyalty_program_v2",
                "note": "Enable enhanced loyalty program with tier benefits",
                "everyone": None,
            },
            {
                "name": "gold_rate_alerts",
                "note": "Enable real-time gold rate alerts and notifications",
                "everyone": None,
            },
            {
                "name": "multi_currency_support",
                "note": "Enable multi-currency support for international operations",
                "everyone": None,
            },
            {
                "name": "offline_pos_mode",
                "note": "Enable offline POS mode with local storage sync",
                "everyone": False,  # Disabled by default, enable per tenant
            },
            {
                "name": "custom_order_tracking",
                "note": "Enable custom order tracking with photo uploads",
                "everyone": True,  # Enabled for everyone
            },
            {
                "name": "webhook_integrations",
                "note": "Enable webhook integrations for external systems",
                "everyone": None,
            },
            {
                "name": "beta_features",
                "note": "Enable beta features for testing (admin only)",
                "everyone": False,
            },
        ]

        for flag_data in flags:
            flag, created = Flag.objects.get_or_create(
                name=flag_data["name"],
                defaults={
                    "note": flag_data["note"],
                    "everyone": flag_data["everyone"],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created flag: {flag_data['name']}"))
            else:
                # Update note if flag exists
                flag.note = flag_data["note"]
                flag.save()
                self.stdout.write(self.style.WARNING(f"⚠ Flag already exists: {flag_data['name']}"))

        # Create Switches (global on/off features)
        switches = [
            {
                "name": "maintenance_mode",
                "note": "Enable maintenance mode (disables tenant access)",
                "active": False,
            },
            {
                "name": "new_tenant_signups",
                "note": "Allow new tenant registrations",
                "active": True,
            },
            {
                "name": "email_notifications",
                "note": "Enable email notifications system-wide",
                "active": True,
            },
            {
                "name": "sms_notifications",
                "note": "Enable SMS notifications system-wide",
                "active": True,
            },
            {
                "name": "backup_system",
                "note": "Enable automated backup system",
                "active": True,
            },
            {
                "name": "gold_rate_sync",
                "note": "Enable automatic gold rate synchronization",
                "active": True,
            },
            {
                "name": "stripe_payments",
                "note": "Enable Stripe payment processing",
                "active": False,  # Disabled until configured
            },
            {
                "name": "debug_mode",
                "note": "Enable debug mode for troubleshooting (admin only)",
                "active": False,
            },
        ]

        for switch_data in switches:
            switch, created = Switch.objects.get_or_create(
                name=switch_data["name"],
                defaults={
                    "note": switch_data["note"],
                    "active": switch_data["active"],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created switch: {switch_data['name']}"))
            else:
                # Update note if switch exists
                switch.note = switch_data["note"]
                switch.save()
                self.stdout.write(
                    self.style.WARNING(f"⚠ Switch already exists: {switch_data['name']}")
                )

        # Create Samples (percentage-based rollout)
        samples = [
            {
                "name": "new_dashboard_layout",
                "note": "Gradual rollout of new dashboard layout",
                "percent": 0.0,  # Start at 0%, gradually increase
            },
            {
                "name": "performance_monitoring",
                "note": "Enable performance monitoring for sample of users",
                "percent": 10.0,  # Monitor 10% of users
            },
            {
                "name": "ab_test_checkout_flow",
                "note": "A/B test for new checkout flow",
                "percent": 50.0,  # 50/50 split
            },
        ]

        for sample_data in samples:
            sample, created = Sample.objects.get_or_create(
                name=sample_data["name"],
                defaults={
                    "note": sample_data["note"],
                    "percent": sample_data["percent"],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created sample: {sample_data['name']}"))
            else:
                # Update note if sample exists
                sample.note = sample_data["note"]
                sample.save()
                self.stdout.write(
                    self.style.WARNING(f"⚠ Sample already exists: {sample_data['name']}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Feature flags setup complete!"
                f"\n  - {len(flags)} flags"
                f"\n  - {len(switches)} switches"
                f"\n  - {len(samples)} samples"
            )
        )
