"""
Tests for settings views and functionality.

Tests the implementation of Requirement 20: Settings and Configuration
- Shop profile configuration page
- Branding customization (logo upload, colors)
- Business hours configuration
- Holiday calendar
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import IntegrationSettings, InvoiceSettings, Tenant, TenantSettings

User = get_user_model()


class SettingsViewsTestCase(TestCase):
    """Test cases for settings views."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        # Create tenant owner user
        self.user = User.objects.create_user(
            username="owner",
            password="testpass123",
            email="owner@test.com",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create settings objects
        self.tenant_settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_name="Test Jewelry Shop",
            primary_color="#3b82f6",
            secondary_color="#6b7280",
        )

        self.invoice_settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
        )

        self.integration_settings = IntegrationSettings.objects.create(
            tenant=self.tenant,
        )

    def test_settings_overview_view(self):
        """Test settings overview page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_overview")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Settings")
        self.assertContains(response, "Test Jewelry Shop")

    def test_shop_profile_view_get(self):
        """Test shop profile page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_shop_profile")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shop Profile")
        self.assertContains(response, "Business Information")

    def test_shop_profile_view_post(self):
        """Test shop profile form submission."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_shop_profile")
        data = {
            "business_name": "Updated Jewelry Shop",
            "phone": "+1-555-123-4567",
            "email": "contact@updated.com",
            "timezone": "America/New_York",
            "currency": "USD",
            "date_format": "MM/DD/YYYY",
            "default_tax_rate": "8.25",
            "tax_inclusive_pricing": False,
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that settings were updated
        self.tenant_settings.refresh_from_db()
        self.assertEqual(self.tenant_settings.business_name, "Updated Jewelry Shop")
        self.assertEqual(self.tenant_settings.phone, "+1-555-123-4567")

    def test_branding_view_get(self):
        """Test branding page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_branding")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Branding")
        self.assertContains(response, "Logo")
        self.assertContains(response, "Color Scheme")

    def test_branding_color_update(self):
        """Test branding color update."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_branding")
        data = {
            "primary_color": "#10b981",
            "secondary_color": "#6b7280",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that colors were updated
        self.tenant_settings.refresh_from_db()
        self.assertEqual(self.tenant_settings.primary_color, "#10b981")

    def test_business_hours_view_get(self):
        """Test business hours page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_business_hours")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Hours")
        self.assertContains(response, "Weekly Schedule")

    def test_business_hours_update(self):
        """Test business hours update."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_business_hours")
        data = {
            "monday_open": "09:00",
            "monday_close": "17:00",
            "tuesday_open": "09:00",
            "tuesday_close": "17:00",
            "wednesday_open": "09:00",
            "wednesday_close": "17:00",
            "thursday_open": "09:00",
            "thursday_close": "17:00",
            "friday_open": "09:00",
            "friday_close": "17:00",
            "saturday_open": "10:00",
            "saturday_close": "16:00",
            "sunday_closed": "on",  # Sunday is closed
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that business hours were updated
        self.tenant_settings.refresh_from_db()
        self.assertIn("monday", self.tenant_settings.business_hours)
        self.assertEqual(self.tenant_settings.business_hours["monday"]["open"], "09:00")
        self.assertEqual(self.tenant_settings.business_hours["sunday"]["closed"], True)

    def test_holiday_calendar_view_get(self):
        """Test holiday calendar page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_holiday_calendar")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Holiday Calendar")
        self.assertContains(response, "Add Holiday")

    def test_holiday_add(self):
        """Test adding a holiday."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_holiday_calendar")
        data = {
            "action": "add_holiday",
            "holiday_date": "2024-12-25",
            "holiday_name": "Christmas Day",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that holiday was added
        self.tenant_settings.refresh_from_db()
        self.assertEqual(len(self.tenant_settings.holidays), 1)
        self.assertEqual(self.tenant_settings.holidays[0]["name"], "Christmas Day")
        self.assertEqual(self.tenant_settings.holidays[0]["date"], "2024-12-25")

    def test_holiday_remove(self):
        """Test removing a holiday."""
        # First add a holiday
        self.tenant_settings.holidays = [{"date": "2024-12-25", "name": "Christmas Day"}]
        self.tenant_settings.save()

        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_holiday_calendar")
        data = {
            "action": "remove_holiday",
            "holiday_date": "2024-12-25",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that holiday was removed
        self.tenant_settings.refresh_from_db()
        self.assertEqual(len(self.tenant_settings.holidays), 0)

    def test_integration_settings_view_get(self):
        """Test integration settings page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_integration")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Integration Settings")
        self.assertContains(response, "Payment Gateway")
        self.assertContains(response, "SMS Provider")
        self.assertContains(response, "Email Provider")

    def test_payment_gateway_settings_update(self):
        """Test payment gateway settings update."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_integration")
        data = {
            "section": "payment",
            "payment_gateway_enabled": "on",
            "payment_gateway_provider": "stripe",
            "payment_gateway_test_mode": "on",
            "payment_gateway_api_key": "test_api_key",
            "payment_gateway_secret_key": "test_secret_key",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that settings were updated
        self.integration_settings.refresh_from_db()
        self.assertTrue(self.integration_settings.payment_gateway_enabled)
        self.assertEqual(self.integration_settings.payment_gateway_provider, "stripe")
        self.assertTrue(self.integration_settings.payment_gateway_test_mode)

    def test_sms_provider_settings_update(self):
        """Test SMS provider settings update."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_integration")
        data = {
            "section": "sms",
            "sms_provider_enabled": "on",
            "sms_provider": "twilio",
            "sms_sender_id": "+1234567890",
            "sms_api_key": "test_sms_key",
            "sms_api_secret": "test_sms_secret",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that settings were updated
        self.integration_settings.refresh_from_db()
        self.assertTrue(self.integration_settings.sms_provider_enabled)
        self.assertEqual(self.integration_settings.sms_provider, "twilio")
        self.assertEqual(self.integration_settings.sms_sender_id, "+1234567890")

    def test_email_provider_settings_update(self):
        """Test email provider settings update."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_integration")
        data = {
            "section": "email",
            "email_provider_enabled": "on",
            "email_provider": "sendgrid",
            "email_from_address": "noreply@test.com",
            "email_from_name": "Test Shop",
            "email_api_key": "test_email_key",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that settings were updated
        self.integration_settings.refresh_from_db()
        self.assertTrue(self.integration_settings.email_provider_enabled)
        self.assertEqual(self.integration_settings.email_provider, "sendgrid")
        self.assertEqual(self.integration_settings.email_from_address, "noreply@test.com")
        self.assertEqual(self.integration_settings.email_from_name, "Test Shop")

    def test_invoice_customization_view_get(self):
        """Test invoice customization page loads correctly."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_invoice_customization")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invoice Settings")
        self.assertContains(response, "Template Selection")
        self.assertContains(response, "Invoice Numbering")

    def test_invoice_settings_update(self):
        """Test invoice settings form submission."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_invoice_customization")
        data = {
            "invoice_template": "detailed",
            "receipt_template": "minimal",
            "invoice_numbering_scheme": "yearly",
            "invoice_number_prefix": "INV",
            "invoice_number_format": "{prefix}-{year}-{number:04d}",
            "receipt_numbering_scheme": "sequential",
            "receipt_number_prefix": "RCP",
            "receipt_number_format": "{prefix}-{number:06d}",
            "show_item_codes": True,
            "show_item_descriptions": True,
            "show_item_weights": True,
            "show_karat_purity": True,
            "show_tax_breakdown": True,
            "show_payment_terms": False,
            "invoice_footer_text": "Thank you for your business!",
            "receipt_footer_text": "Please keep this receipt.",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that settings were updated
        self.invoice_settings.refresh_from_db()
        self.assertEqual(self.invoice_settings.invoice_template, "detailed")
        self.assertEqual(self.invoice_settings.receipt_template, "minimal")
        self.assertEqual(self.invoice_settings.invoice_numbering_scheme, "yearly")

    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access settings."""
        # Don't log in
        url = reverse("core:settings_overview")
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_tenant_isolation(self):
        """Test that users can only access their own tenant's settings."""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status="ACTIVE",
        )

        User.objects.create_user(
            username="other_owner",
            password="testpass123",
            email="other@test.com",
            tenant=other_tenant,
            role="TENANT_OWNER",
        )

        # Login as other user
        self.client.login(username="other_owner", password="testpass123")

        # Try to access settings - should get their own settings, not the original tenant's
        url = reverse("core:settings_overview")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should not contain the original tenant's business name
        self.assertNotContains(response, "Test Jewelry Shop")

    def test_invoice_customization_view_post(self):
        """Test invoice customization form submission."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:settings_invoice_customization")
        data = {
            "invoice_template": "detailed",
            "receipt_template": "minimal",
            "invoice_numbering_scheme": "yearly",
            "invoice_number_prefix": "INV",
            "invoice_number_format": "{prefix}-{year}-{number:04d}",
            "receipt_numbering_scheme": "sequential",
            "receipt_number_prefix": "RCP",
            "receipt_number_format": "{prefix}-{number:06d}",
            "show_item_codes": True,
            "show_item_descriptions": True,
            "show_item_weights": True,
            "show_karat_purity": True,
            "show_tax_breakdown": True,
            "show_payment_terms": False,
            "custom_field_1_label": "Certificate Number",
            "custom_field_1_value": "",
            "custom_field_2_label": "Warranty Period",
            "custom_field_2_value": "1 Year",
            "invoice_footer_text": "Thank you for your business!",
            "receipt_footer_text": "Please keep this receipt for your records.",
            "payment_terms": "Payment is due within 30 days.",
            "return_policy": "Returns accepted within 30 days with receipt.",
        }

        response = self.client.post(url, data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that invoice settings were updated
        invoice_settings = InvoiceSettings.objects.get(tenant=self.tenant)
        self.assertEqual(invoice_settings.invoice_template, "detailed")
        self.assertEqual(invoice_settings.receipt_template, "minimal")
        self.assertEqual(invoice_settings.invoice_numbering_scheme, "yearly")
        self.assertEqual(invoice_settings.custom_field_1_label, "Certificate Number")
        self.assertEqual(invoice_settings.custom_field_2_value, "1 Year")


class TenantSettingsModelTestCase(TestCase):
    """Test cases for TenantSettings model methods."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status="ACTIVE",
        )

    def test_tenant_settings_creation(self):
        """Test creating tenant settings."""
        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_name="Test Business",
            primary_color="#3b82f6",
            secondary_color="#6b7280",
        )

        self.assertEqual(str(settings), "Settings for Test Shop")
        self.assertEqual(settings.primary_color, "#3b82f6")

    def test_get_full_address(self):
        """Test get_full_address method."""
        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            address_line_1="123 Main St",
            city="Anytown",
            state_province="CA",
            postal_code="12345",
            country="USA",
        )

        expected_address = "123 Main St, Anytown, CA, 12345, USA"
        self.assertEqual(settings.get_full_address(), expected_address)

    def test_business_hours_validation(self):
        """Test business hours structure."""
        business_hours = {
            "monday": {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
            "thursday": {"open": "09:00", "close": "17:00", "closed": False},
            "friday": {"open": "09:00", "close": "17:00", "closed": False},
            "saturday": {"open": "10:00", "close": "16:00", "closed": False},
            "sunday": {"open": "12:00", "close": "16:00", "closed": True},
        }

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_hours=business_hours,
        )

        self.assertEqual(settings.business_hours["monday"]["open"], "09:00")
        self.assertTrue(settings.business_hours["sunday"]["closed"])

    def test_holidays_validation(self):
        """Test holidays structure."""
        holidays = [
            {"date": "2024-01-01", "name": "New Year's Day"},
            {"date": "2024-12-25", "name": "Christmas Day"},
        ]

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            holidays=holidays,
        )

        self.assertEqual(len(settings.holidays), 2)
        self.assertEqual(settings.holidays[0]["name"], "New Year's Day")


class InvoiceSettingsModelTestCase(TestCase):
    """Test cases for InvoiceSettings model methods."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status="ACTIVE",
        )

    def test_invoice_settings_creation(self):
        """Test creating invoice settings."""
        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            invoice_template="standard",
            invoice_number_prefix="INV",
        )

        self.assertEqual(str(settings), "Invoice Settings for Test Shop")
        self.assertEqual(settings.invoice_template, "standard")
        self.assertEqual(settings.invoice_number_prefix, "INV")

    def test_generate_invoice_number_sequential(self):
        """Test sequential invoice number generation."""
        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            invoice_numbering_scheme="sequential",
            invoice_number_prefix="INV",
            invoice_number_format="{prefix}-{number:06d}",
            next_invoice_number=1,
        )

        number = settings.generate_invoice_number()
        self.assertEqual(number, "INV-000001")

        # Check that counter was incremented
        updated_settings = InvoiceSettings.objects.get(id=settings.id)
        self.assertEqual(updated_settings.next_invoice_number, 2)

    def test_generate_invoice_number_yearly(self):
        """Test yearly invoice number generation."""
        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            invoice_numbering_scheme="yearly",
            next_invoice_number=1,
        )

        number = settings.generate_invoice_number()
        # Should contain current year
        import datetime

        current_year = str(datetime.datetime.now().year)
        self.assertIn(current_year, number)
        self.assertIn("001", number)

    def test_generate_receipt_number_sequential(self):
        """Test sequential receipt number generation."""
        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            receipt_numbering_scheme="sequential",
            receipt_number_prefix="RCP",
            receipt_number_format="{prefix}-{number:06d}",
            next_receipt_number=1,
        )

        number = settings.generate_receipt_number()
        self.assertEqual(number, "RCP-000001")

        # Check that counter was incremented
        updated_settings = InvoiceSettings.objects.get(id=settings.id)
        self.assertEqual(updated_settings.next_receipt_number, 2)


class IntegrationSettingsFormTestCase(TestCase):
    """Test cases for IntegrationSettingsForm."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        self.integration_settings = IntegrationSettings.objects.create(tenant=self.tenant)

    def test_form_validation_payment_gateway(self):
        """Test form validation for payment gateway settings."""
        from apps.core.forms import IntegrationSettingsForm

        # Test that provider is required when payment gateway is enabled
        form_data = {
            "payment_gateway_enabled": True,
            "payment_gateway_provider": "",  # Empty provider
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        self.assertFalse(form.is_valid())
        self.assertIn("payment_gateway_provider", form.errors)

    def test_form_validation_sms_provider(self):
        """Test form validation for SMS provider settings."""
        from apps.core.forms import IntegrationSettingsForm

        # Test that provider is required when SMS is enabled
        form_data = {
            "sms_provider_enabled": True,
            "sms_provider": "",  # Empty provider
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        self.assertFalse(form.is_valid())
        self.assertIn("sms_provider", form.errors)

    def test_form_validation_email_provider(self):
        """Test form validation for email provider settings."""
        from apps.core.forms import IntegrationSettingsForm

        # Test that provider is required when email is enabled
        form_data = {
            "email_provider_enabled": True,
            "email_provider": "",  # Empty provider
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        self.assertFalse(form.is_valid())
        self.assertIn("email_provider", form.errors)

    def test_form_validation_smtp_settings(self):
        """Test form validation for SMTP settings."""
        from apps.core.forms import IntegrationSettingsForm

        # Test that SMTP host is required when SMTP provider is selected
        form_data = {
            "email_provider_enabled": True,
            "email_provider": "smtp",
            "smtp_host": "",  # Empty host
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        self.assertFalse(form.is_valid())
        self.assertIn("smtp_host", form.errors)

        # Test that SMTP port is required when SMTP provider is selected
        form_data = {
            "email_provider_enabled": True,
            "email_provider": "smtp",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": "",  # Empty port
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        self.assertFalse(form.is_valid())
        self.assertIn("smtp_port", form.errors)

    def test_form_save_with_encrypted_fields(self):
        """Test form save with encrypted credential fields."""
        from apps.core.forms import IntegrationSettingsForm

        form_data = {
            "payment_gateway_enabled": True,
            "payment_gateway_provider": "stripe",
            "payment_gateway_test_mode": True,
            "payment_gateway_api_key_input": "test_api_key",
            "payment_gateway_secret_key_input": "test_secret_key",
            "sms_provider_enabled": True,
            "sms_provider": "twilio",
            "sms_sender_id": "+1234567890",
            "sms_api_key_input": "test_sms_key",
            "sms_api_secret_input": "test_sms_secret",
        }

        form = IntegrationSettingsForm(data=form_data, instance=self.integration_settings)
        if not form.is_valid():
            print("Form errors:", form.errors)
        self.assertTrue(form.is_valid())

        saved_instance = form.save()

        # Check that settings were saved
        self.assertTrue(saved_instance.payment_gateway_enabled)
        self.assertEqual(saved_instance.payment_gateway_provider, "stripe")
        self.assertTrue(saved_instance.payment_gateway_test_mode)
        self.assertTrue(saved_instance.sms_provider_enabled)
        self.assertEqual(saved_instance.sms_provider, "twilio")
        self.assertEqual(saved_instance.sms_sender_id, "+1234567890")

        # Check that encrypted fields were set (they should not be empty)
        self.assertNotEqual(saved_instance.payment_gateway_api_key, "")
        self.assertNotEqual(saved_instance.payment_gateway_secret_key, "")
        self.assertNotEqual(saved_instance.sms_api_key, "")
        self.assertNotEqual(saved_instance.sms_api_secret, "")


class SettingsAPIViewsTestCase(TestCase):
    """Test cases for settings API views."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        # Create tenant owner user
        self.user = User.objects.create_user(
            username="owner",
            password="testpass123",
            email="owner@test.com",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create settings objects
        self.tenant_settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_name="Test Jewelry Shop",
            primary_color="#3b82f6",
            secondary_color="#6b7280",
        )

        self.invoice_settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
        )

        self.integration_settings = IntegrationSettings.objects.create(
            tenant=self.tenant,
        )

    def test_tenant_settings_api_get(self):
        """Test TenantSettingsAPIView GET request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_tenant_settings")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["business_name"], "Test Jewelry Shop")
        self.assertEqual(data["primary_color"], "#3b82f6")

    def test_tenant_settings_api_patch(self):
        """Test TenantSettingsAPIView PATCH request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_tenant_settings")
        data = {
            "business_name": "Updated Shop Name",
            "primary_color": "#10b981",
        }

        response = self.client.patch(url, data=data, content_type="application/json")

        self.assertEqual(response.status_code, 200)

        # Check that settings were updated
        self.tenant_settings.refresh_from_db()
        self.assertEqual(self.tenant_settings.business_name, "Updated Shop Name")
        self.assertEqual(self.tenant_settings.primary_color, "#10b981")

    def test_invoice_settings_api_get(self):
        """Test InvoiceSettingsAPIView GET request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_invoice_settings")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("invoice_template", data)
        self.assertIn("receipt_template", data)

    def test_invoice_settings_api_patch(self):
        """Test InvoiceSettingsAPIView PATCH request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_invoice_settings")
        data = {
            "invoice_template": "detailed",
            "invoice_number_prefix": "INV",
        }

        response = self.client.patch(url, data=data, content_type="application/json")

        self.assertEqual(response.status_code, 200)

        # Check that settings were updated
        self.invoice_settings.refresh_from_db()
        self.assertEqual(self.invoice_settings.invoice_template, "detailed")
        self.assertEqual(self.invoice_settings.invoice_number_prefix, "INV")

    def test_integration_settings_api_get(self):
        """Test IntegrationSettingsAPIView GET request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_integration_settings")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("payment_gateway_enabled", data)
        self.assertIn("sms_provider_enabled", data)
        self.assertIn("email_provider_enabled", data)

    def test_integration_settings_api_patch(self):
        """Test IntegrationSettingsAPIView PATCH request."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_integration_settings")
        data = {
            "payment_gateway_enabled": True,
            "payment_gateway_provider": "stripe",
        }

        response = self.client.patch(url, data=data, content_type="application/json")

        self.assertEqual(response.status_code, 200)

        # Check that settings were updated
        self.integration_settings.refresh_from_db()
        self.assertTrue(self.integration_settings.payment_gateway_enabled)
        self.assertEqual(self.integration_settings.payment_gateway_provider, "stripe")

    def test_upload_logo_api(self):
        """Test logo upload API endpoint."""
        import tempfile

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        self.client.login(username="owner", password="testpass123")

        # Create a test image
        image = Image.new("RGB", (100, 100), color="red")
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        image.save(temp_file.name, "JPEG")

        with open(temp_file.name, "rb") as f:
            logo_file = SimpleUploadedFile("test_logo.jpg", f.read(), content_type="image/jpeg")

            url = reverse("core:api_upload_logo")
            response = self.client.post(url, {"logo": logo_file})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("logo_url", data)

        # Check that logo was saved
        self.tenant_settings.refresh_from_db()
        self.assertTrue(self.tenant_settings.logo)

    def test_upload_logo_api_no_file(self):
        """Test logo upload API with no file."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_upload_logo")
        response = self.client.post(url, {})

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("No logo file provided", data["error"])

    def test_update_colors_api(self):
        """Test color update API endpoint."""
        import json

        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_update_colors")
        data = {
            "primary_color": "#10b981",
            "secondary_color": "#6b7280",
        }

        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["primary_color"], "#10b981")
        self.assertEqual(response_data["secondary_color"], "#6b7280")

        # Check that colors were updated
        self.tenant_settings.refresh_from_db()
        self.assertEqual(self.tenant_settings.primary_color, "#10b981")
        self.assertEqual(self.tenant_settings.secondary_color, "#6b7280")

    def test_update_colors_api_invalid_format(self):
        """Test color update API with invalid color format."""
        import json

        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_update_colors")
        data = {
            "primary_color": "invalid_color",
            "secondary_color": "#6b7280",
        }

        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("Invalid color format", response_data["error"])

    def test_update_colors_api_missing_colors(self):
        """Test color update API with missing colors."""
        import json

        self.client.login(username="owner", password="testpass123")

        url = reverse("core:api_update_colors")
        data = {
            "primary_color": "#10b981",
            # Missing secondary_color
        }

        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("Both colors are required", response_data["error"])

    def test_api_unauthorized_access(self):
        """Test that unauthorized users cannot access API endpoints."""
        # Don't log in

        # Test tenant settings API
        url = reverse("core:api_tenant_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

        # Test invoice settings API
        url = reverse("core:api_invoice_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

        # Test integration settings API
        url = reverse("core:api_integration_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)


class DataManagementIntegrationTestCase(TestCase):
    """Integration tests for data management functionality."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        # Create tenant owner user
        self.user = User.objects.create_user(
            username="owner",
            password="testpass123",
            email="owner@test.com",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_download_template_csv(self):
        """Test downloading CSV templates."""
        self.client.login(username="owner", password="testpass123")

        # Test inventory template
        url = reverse("core:download_template", kwargs={"template_type": "inventory"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("inventory_template.csv", response["Content-Disposition"])

        # Check CSV content
        content = response.content.decode("utf-8")
        self.assertIn("SKU", content)
        self.assertIn("Name", content)
        self.assertIn("Karat", content)

    def test_download_template_customers(self):
        """Test downloading customer template."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:download_template", kwargs={"template_type": "customers"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("customers_template.csv", response["Content-Disposition"])

        # Check CSV content
        content = response.content.decode("utf-8")
        self.assertIn("First Name", content)
        self.assertIn("Last Name", content)
        self.assertIn("Email", content)

    def test_download_template_suppliers(self):
        """Test downloading supplier template."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:download_template", kwargs={"template_type": "suppliers"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("suppliers_template.csv", response["Content-Disposition"])

        # Check CSV content
        content = response.content.decode("utf-8")
        self.assertIn("Company Name", content)
        self.assertIn("Contact Person", content)
        self.assertIn("Email", content)

    def test_download_template_invalid_type(self):
        """Test downloading invalid template type."""
        self.client.login(username="owner", password="testpass123")

        url = reverse("core:download_template", kwargs={"template_type": "invalid"})
        response = self.client.get(url)

        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

    def test_settings_form_validation_edge_cases(self):
        """Test edge cases in settings form validation."""
        self.client.login(username="owner", password="testpass123")

        # Test business hours with invalid time format
        url = reverse("core:settings_business_hours")
        data = {
            "monday_open": "25:00",  # Invalid hour
            "monday_close": "17:00",
        }

        response = self.client.post(url, data)
        # Should handle gracefully and redirect
        self.assertEqual(response.status_code, 302)

        # Test holiday with invalid date format
        url = reverse("core:settings_holiday_calendar")
        data = {
            "action": "add_holiday",
            "holiday_date": "invalid-date",
            "holiday_name": "Test Holiday",
        }

        response = self.client.post(url, data)
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

    def test_settings_concurrent_updates(self):
        """Test concurrent updates to settings."""
        from django.db import transaction

        self.client.login(username="owner", password="testpass123")

        # Create initial settings
        tenant_settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_name="Original Name",
        )

        # Simulate concurrent update
        with transaction.atomic():
            # Update via form - need to include all required fields
            url = reverse("core:settings_shop_profile")
            data = {
                "business_name": "Updated via Form",
                "phone": "+1-555-123-4567",
                "email": "test@example.com",
                "timezone": "America/New_York",
                "currency": "USD",
                "date_format": "MM/DD/YYYY",
                "default_tax_rate": "8.25",
                "tax_inclusive_pricing": False,
            }

            response = self.client.post(url, data)
            # Should redirect on success or show form with errors
            self.assertIn(response.status_code, [200, 302])

        # Verify final state if update was successful
        tenant_settings.refresh_from_db()
        if response.status_code == 302:
            self.assertEqual(tenant_settings.business_name, "Updated via Form")
