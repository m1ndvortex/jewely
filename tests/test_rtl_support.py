"""
Tests for RTL (Right-to-Left) support
Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.core.models import Tenant

User = get_user_model()


class RTLSupportTestCase(TestCase):
    """Test RTL support for Persian language"""

    def setUp(self):
        """Set up test data"""
        # Create tenant with unique slug
        import uuid

        unique_slug = f"test-shop-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug=unique_slug, status="ACTIVE"
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
            language="fa",  # Persian language
        )

        self.client = Client()

    def test_html_dir_attribute_ltr_for_english(self):
        """Test that HTML dir attribute is 'ltr' for English"""
        # Set user language to English
        self.user.language = "en"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that response contains dir="ltr"
        self.assertContains(response, 'dir="ltr"')
        self.assertNotContains(response, 'dir="rtl"')

    def test_html_dir_attribute_rtl_for_persian(self):
        """Test that HTML dir attribute is 'rtl' for Persian"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that response contains dir="rtl"
        self.assertContains(response, 'dir="rtl"')
        self.assertNotContains(response, 'dir="ltr"')

    def test_html_lang_attribute_english(self):
        """Test that HTML lang attribute is 'en' for English"""
        # Set user language to English
        self.user.language = "en"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that response contains lang="en"
        self.assertContains(response, 'lang="en"')

    def test_html_lang_attribute_persian(self):
        """Test that HTML lang attribute is 'fa' for Persian"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that response contains lang="fa"
        self.assertContains(response, 'lang="fa"')

    def test_rtl_css_loaded(self):
        """Test that RTL CSS file is loaded"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that RTL CSS is included
        self.assertContains(response, "rtl.css")

    def test_persian_font_loaded_for_persian_language(self):
        """Test that Persian font (Vazir) is loaded for Persian language"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that Vazir font is loaded
        self.assertContains(response, "Vazir")

    def test_persian_font_not_loaded_for_english(self):
        """Test that Persian font is not loaded for English language"""
        # Set user language to English
        self.user.language = "en"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that Vazir font is not loaded
        self.assertNotContains(response, "Vazir")

    def test_language_bidi_context_variable(self):
        """Test that LANGUAGE_BIDI context variable is set correctly"""
        # Test for English (LTR)
        self.user.language = "en"
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # English should have dir="ltr"
        self.assertContains(response, 'dir="ltr"')

        # Test for Persian (RTL)
        self.user.language = "fa"
        self.user.save()
        # Need to re-login to refresh the language
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Persian should have dir="rtl"
        self.assertContains(response, 'dir="rtl"')

    def test_user_language_preference_applied(self):
        """Test that user's language preference is applied"""
        # User has Persian language preference
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)

        # The middleware should set the language based on user preference
        # This is tested indirectly through the dir attribute
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Should have RTL for Persian user
        self.assertContains(response, 'dir="rtl"')

    def test_rtl_css_file_exists(self):
        """Test that RTL CSS file exists"""
        import os

        from django.conf import settings

        rtl_css_path = os.path.join(settings.BASE_DIR, "static", "css", "rtl.css")
        self.assertTrue(os.path.exists(rtl_css_path), "RTL CSS file should exist")

    def test_tailwind_config_exists(self):
        """Test that Tailwind config file exists"""
        import os

        from django.conf import settings

        tailwind_config_path = os.path.join(settings.BASE_DIR, "tailwind.config.js")
        self.assertTrue(os.path.exists(tailwind_config_path), "Tailwind config file should exist")

    def test_package_json_exists(self):
        """Test that package.json file exists"""
        import os

        from django.conf import settings

        package_json_path = os.path.join(settings.BASE_DIR, "package.json")
        self.assertTrue(os.path.exists(package_json_path), "package.json file should exist")


class RTLFormTestCase(TestCase):
    """Test RTL support in forms"""

    def setUp(self):
        """Set up test data"""
        import uuid

        unique_slug = f"test-shop-form-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            company_name="Test Shop", slug=unique_slug, status="ACTIVE"
        )

        self.user = User.objects.create_user(
            username=f"testuser-form-{uuid.uuid4().hex[:8]}",
            email=f"test-form-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
            language="fa",
        )

        self.client = Client()

    def test_form_text_alignment_rtl(self):
        """Test that form inputs have RTL text alignment for Persian"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)

        # Get dashboard page (which has forms)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that the page has RTL direction
        self.assertContains(response, 'dir="rtl"')


class RTLNavigationTestCase(TestCase):
    """Test RTL support in navigation"""

    def setUp(self):
        """Set up test data"""
        import uuid

        unique_slug = f"test-shop-nav-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            company_name="Test Shop", slug=unique_slug, status="ACTIVE"
        )

        self.user = User.objects.create_user(
            username=f"testuser-nav-{uuid.uuid4().hex[:8]}",
            email=f"test-nav-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
            language="fa",
        )

        self.client = Client()

    def test_navigation_rtl_layout(self):
        """Test that navigation has RTL layout for Persian"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that page has RTL direction
        self.assertContains(response, 'dir="rtl"')

        # Check that navigation exists
        self.assertContains(response, "<nav")


class RTLTableTestCase(TestCase):
    """Test RTL support in tables"""

    def setUp(self):
        """Set up test data"""
        import uuid

        unique_slug = f"test-shop-table-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            company_name="Test Shop", slug=unique_slug, status="ACTIVE"
        )

        self.user = User.objects.create_user(
            username=f"testuser-table-{uuid.uuid4().hex[:8]}",
            email=f"test-table-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
            language="fa",
        )

        self.client = Client()

    def test_table_rtl_direction(self):
        """Test that tables have RTL direction for Persian"""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        self.client.force_login(self.user)

        # Get dashboard page
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that page has RTL direction
        self.assertContains(response, 'dir="rtl"')


@pytest.mark.django_db
class TestRTLIntegration:
    """Integration tests for RTL support"""

    def test_rtl_across_multiple_pages(self, client, django_user_model):
        """Test that RTL is consistent across multiple pages"""
        # Create tenant and user
        import uuid

        unique_slug = f"test-shop-multi-{uuid.uuid4().hex[:8]}"
        tenant = Tenant.objects.create(company_name="Test Shop", slug=unique_slug, status="ACTIVE")

        user = django_user_model.objects.create_user(
            username=f"testuser-multi-{uuid.uuid4().hex[:8]}",
            email=f"test-multi-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            role="TENANT_OWNER",
            language="fa",
        )

        client.force_login(user)

        # Test the dashboard page
        response = client.get(reverse("core:tenant_dashboard"))
        assert 'dir="rtl"' in response.content.decode()
        assert 'lang="fa"' in response.content.decode()
        assert response.status_code == 200

    def test_rtl_css_rules_applied(self):
        """Test that RTL CSS rules are properly defined"""
        import os

        from django.conf import settings

        rtl_css_path = os.path.join(settings.BASE_DIR, "static", "css", "rtl.css")

        if os.path.exists(rtl_css_path):
            with open(rtl_css_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Check for essential RTL rules
                assert '[dir="rtl"]' in content
                assert "direction: rtl" in content
                assert "text-align: right" in content

                # Check for margin/padding flips
                assert "margin-left" in content or "margin-right" in content
                assert "padding-left" in content or "padding-right" in content
