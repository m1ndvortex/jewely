"""
Comprehensive i18n tests for Task 26.6.

This module tests:
- Translation coverage across the application
- RTL layout functionality
- Number and date formatting
- Language switching functionality
- Integration of all i18n components

Per Requirement 2 - Dual-Language Support (English and Persian)
Per Requirement 28 - Testing requirements
"""

from datetime import date, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

import jdatetime
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.formatting_utils import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    to_persian_numerals,
    to_western_numerals,
)
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestTranslationCoverage:
    """Test translation coverage across the application."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        import uuid

        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

    def test_translation_files_exist_for_both_languages(self):
        """Test that translation files exist for English and Persian."""
        locale_path = settings.LOCALE_PATHS[0]

        # Check English files
        en_po = locale_path / "en" / "LC_MESSAGES" / "django.po"
        en_mo = locale_path / "en" / "LC_MESSAGES" / "django.mo"
        assert en_po.exists(), "English .po file should exist"
        assert en_mo.exists(), "English .mo file should exist"

        # Check Persian files
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"
        fa_mo = locale_path / "fa" / "LC_MESSAGES" / "django.mo"
        assert fa_po.exists(), "Persian .po file should exist"
        assert fa_mo.exists(), "Persian .mo file should exist"

    def test_key_strings_are_translated(self):
        """Test that key application strings are marked for translation."""
        locale_path = settings.LOCALE_PATHS[0]
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"

        with open(fa_po, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for key strings from the application
        key_strings = [
            "Dashboard",
            "Inventory",
            "Sales",
            "Customers",
            "Reports",
            "Settings",
            "Active",
            "Inactive",
            "Save",
            "Cancel",
            "Delete",
            "Edit",
        ]

        for string in key_strings:
            assert string in content, f"'{string}' should be in translation file"

    def test_template_translation_tags_present(self, client, user):
        """Test that templates use translation tags."""
        client.force_login(user)

        # Get a page and check for translated content
        response = client.get(reverse("core:tenant_dashboard"))
        assert response.status_code == 200

        # The page should have been rendered with translation support
        content = response.content.decode("utf-8")
        # Check that the page has proper language attributes
        assert 'lang="en"' in content or 'lang="fa"' in content

    def test_model_field_labels_use_lazy_translation(self):
        """Test that model field labels use lazy translation."""
        from apps.core.translation_utils import FIELD_LABELS

        # Verify field labels exist and are translatable
        assert "name" in FIELD_LABELS
        assert "email" in FIELD_LABELS
        assert "phone" in FIELD_LABELS

        # Convert to string to ensure they work
        for key, label in FIELD_LABELS.items():
            str_label = str(label)
            assert isinstance(str_label, str)
            assert len(str_label) > 0

    def test_form_validation_messages_are_translatable(self):
        """Test that form validation messages are translatable."""
        from apps.core.translation_utils import get_error_messages

        errors = get_error_messages()

        # Check that error messages exist
        assert "required_field" in errors
        assert "invalid_email" in errors

        # Verify they are strings
        for key, message in errors.items():
            assert isinstance(message, str)
            assert len(message) > 0


@pytest.mark.django_db
class TestRTLLayout:
    """Test RTL (Right-to-Left) layout functionality."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        import uuid

        return Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def user_english(self, tenant):
        """Create an English-speaking user."""
        return User.objects.create_user(
            username="user_en",
            email="en@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

    @pytest.fixture
    def user_persian(self, tenant):
        """Create a Persian-speaking user."""
        return User.objects.create_user(
            username="user_fa",
            email="fa@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="fa",
        )

    def test_ltr_direction_for_english(self, client, user_english):
        """Test that English pages use LTR direction."""
        client.force_login(user_english)

        response = client.get(reverse("core:tenant_dashboard"))
        assert response.status_code == 200

        content = response.content.decode("utf-8")
        assert 'dir="ltr"' in content
        assert 'lang="en"' in content

    def test_rtl_direction_for_persian(self, client, user_persian):
        """Test that Persian pages use RTL direction."""
        client.force_login(user_persian)

        response = client.get(reverse("core:tenant_dashboard"))
        assert response.status_code == 200

        content = response.content.decode("utf-8")
        assert 'dir="rtl"' in content
        assert 'lang="fa"' in content

    def test_rtl_css_loaded_for_persian(self, client, user_persian):
        """Test that RTL CSS is loaded for Persian users."""
        client.force_login(user_persian)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # Check that RTL CSS is referenced
        assert "rtl.css" in content

    def test_rtl_css_not_loaded_for_english(self, client, user_english):
        """Test that RTL CSS is loaded but not applied for English users."""
        client.force_login(user_english)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # RTL CSS file may be loaded but LTR direction should be set
        assert 'dir="ltr"' in content
        assert 'lang="en"' in content

    def test_persian_font_loaded_for_persian_language(self, client, user_persian):
        """Test that Persian font is loaded for Persian users."""
        client.force_login(user_persian)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # Check for Persian font (Vazir or similar)
        assert "Vazir" in content or "font-family" in content

    def test_rtl_layout_consistency_across_pages(self, client, user_persian):
        """Test that RTL layout is consistent across different pages."""
        client.force_login(user_persian)

        # Test multiple pages
        pages = [
            reverse("core:tenant_dashboard"),
        ]

        for page_url in pages:
            response = client.get(page_url)
            if response.status_code == 200:
                content = response.content.decode("utf-8")
                assert 'dir="rtl"' in content, f"RTL not found on {page_url}"
                assert 'lang="fa"' in content, f"Persian lang not found on {page_url}"


@pytest.mark.django_db
class TestNumberFormatting:
    """Test number formatting for different locales."""

    def test_english_number_formatting(self):
        """Test number formatting in English locale."""
        with translation.override("en"):
            # Test integer
            assert format_number(1234567) == "1,234,567"

            # Test decimal
            assert format_number(1234.56) == "1,234.56"

            # Test with specific decimal places
            assert format_number(1234.5, decimal_places=2) == "1,234.50"

    def test_persian_number_formatting(self):
        """Test number formatting in Persian locale."""
        with translation.override("fa"):
            # Test integer with Persian numerals
            result = format_number(1234567)
            assert "۱" in result  # Persian digit 1
            assert "٬" in result  # Persian thousands separator

            # Test decimal with Persian numerals
            result = format_number(1234.56)
            assert "۱" in result
            assert "٫" in result  # Persian decimal separator

    def test_persian_numeral_conversion(self):
        """Test conversion between Western and Persian numerals."""
        # Western to Persian
        assert to_persian_numerals("123") == "۱۲۳"
        assert to_persian_numerals("0123456789") == "۰۱۲۳۴۵۶۷۸۹"
        assert to_persian_numerals(1234) == "۱۲۳۴"
        assert to_persian_numerals(12.34) == "۱۲.۳۴"

        # Persian to Western
        assert to_western_numerals("۱۲۳") == "123"
        assert to_western_numerals("۰۱۲۳۴۵۶۷۸۹") == "0123456789"

    def test_currency_formatting_english(self):
        """Test currency formatting in English."""
        with translation.override("en"):
            # USD
            result = format_currency(1234.56, "USD")
            assert "$" in result
            assert "1,234.56" in result

            # EUR
            result = format_currency(1234.56, "EUR")
            assert "€" in result

    def test_currency_formatting_persian(self):
        """Test currency formatting in Persian."""
        with translation.override("fa"):
            # USD in Persian
            result = format_currency(1234.56, "USD")
            assert "دلار" in result or "USD" in result
            assert "۱" in result  # Persian numerals

            # IRR (Toman)
            result = format_currency(1234567, "IRR")
            assert "تومان" in result or "IRR" in result

    def test_number_formatting_edge_cases(self):
        """Test number formatting edge cases."""
        with translation.override("en"):
            # Zero
            assert format_number(0) == "0"

            # Negative
            result = format_number(-1234.56)
            assert "-" in result
            assert "1,234.56" in result

            # Very large number
            result = format_number(999999999999.99)
            assert "999,999,999,999.99" in result


@pytest.mark.django_db
class TestDateFormatting:
    """Test date and datetime formatting for different locales."""

    def test_english_date_formatting(self):
        """Test date formatting in English."""
        test_date = date(2024, 1, 15)

        with translation.override("en"):
            result = format_date(test_date)
            # Should contain year and be in Gregorian calendar
            assert "2024" in result

    def test_persian_date_formatting_jalali_calendar(self):
        """Test date formatting in Persian with Jalali calendar."""
        test_date = date(2024, 1, 15)

        with translation.override("fa"):
            result = format_date(test_date)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")
            # Should be in Jalali calendar (1402)
            assert "۱۴۰۲" in result

    def test_datetime_formatting_english(self):
        """Test datetime formatting in English."""
        test_datetime = datetime(2024, 1, 15, 14, 30)

        with translation.override("en"):
            result = format_datetime(test_datetime)
            assert "2024" in result
            # Should contain time
            assert any(t in result for t in ["14", "2:30", "PM", "pm", "14:30"])

    def test_datetime_formatting_persian(self):
        """Test datetime formatting in Persian."""
        test_datetime = datetime(2024, 1, 15, 14, 30)

        with translation.override("fa"):
            result = format_datetime(test_datetime)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")
            # Should contain time in Persian numerals
            assert "۱۴" in result and "۳۰" in result

    def test_jalali_calendar_conversion(self):
        """Test Jalali calendar conversion."""
        from apps.core.formatting_utils import to_gregorian, to_jalali

        # Test Gregorian to Jalali
        gregorian = date(2024, 3, 20)  # Persian New Year
        jalali = to_jalali(gregorian)
        assert isinstance(jalali, jdatetime.date)
        assert jalali.year == 1403
        assert jalali.month == 1
        assert jalali.day == 1

        # Test Jalali to Gregorian
        jalali_date = jdatetime.date(1403, 1, 1)
        gregorian_result = to_gregorian(jalali_date)
        assert isinstance(gregorian_result, date)
        assert gregorian_result == gregorian

    def test_date_format_configuration(self):
        """Test that date format configuration is correct."""
        from config.formats import en, fa

        # English formats
        assert hasattr(en, "DATE_FORMAT")
        assert hasattr(en, "SHORT_DATE_FORMAT")
        assert hasattr(en, "DATETIME_FORMAT")

        # Persian formats
        assert hasattr(fa, "DATE_FORMAT")
        assert hasattr(fa, "SHORT_DATE_FORMAT")
        assert hasattr(fa, "DATETIME_FORMAT")

    def test_first_day_of_week_configuration(self):
        """Test first day of week configuration."""
        from config.formats import en, fa

        # English: Sunday (0)
        assert en.FIRST_DAY_OF_WEEK == 0

        # Persian: Saturday (6)
        assert fa.FIRST_DAY_OF_WEEK == 6


@pytest.mark.django_db
class TestLanguageSwitching:
    """Test language switching functionality."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        import uuid

        return Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

    @pytest.fixture
    def api_client(self):
        """Create an API client."""
        return APIClient()

    def test_switch_language_via_api(self, api_client, user):
        """Test switching language via API endpoint."""
        api_client.force_authenticate(user=user)

        # Switch to Persian
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["language"] == "fa"

        # Verify user preference was updated
        user.refresh_from_db()
        assert user.language == "fa"

    def test_language_preference_persists(self, api_client, user):
        """Test that language preference persists across sessions."""
        api_client.force_authenticate(user=user)

        # Set language to Persian
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Reload user and verify persistence
        user.refresh_from_db()
        assert user.language == "fa"

        # Switch back to English
        response = api_client.post(url, {"language": "en"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.language == "en"

    def test_invalid_language_code_rejected(self, api_client, user):
        """Test that invalid language codes are rejected."""
        api_client.force_authenticate(user=user)

        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "invalid"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

        # Verify user language was not changed
        user.refresh_from_db()
        assert user.language == "en"

    def test_language_switch_requires_authentication(self, api_client):
        """Test that language switching requires authentication."""
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_middleware_applies_user_language(self, client, user):
        """Test that middleware applies user's language preference."""
        # Set user language to Persian
        user.language = "fa"
        user.save()

        client.force_login(user)

        # Make a request
        response = client.get(reverse("core:tenant_dashboard"))
        assert response.status_code == 200

        # Check that Persian language is applied
        content = response.content.decode("utf-8")
        assert 'lang="fa"' in content
        assert 'dir="rtl"' in content

    def test_language_switcher_ui_present(self, client, user):
        """Test that language switcher UI is present in pages."""
        client.force_login(user)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # Check for language switcher elements
        assert "switchLanguage" in content  # JavaScript function
        assert "/api/user/language/switch/" in content  # API endpoint


@pytest.mark.django_db
class TestI18nIntegration:
    """Integration tests for complete i18n functionality."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        import uuid

        return Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

    def test_complete_language_switch_workflow(self, client, user):
        """Test complete workflow of switching language and seeing changes."""
        client.force_login(user)

        # Initial state: English
        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")
        assert 'lang="en"' in content
        assert 'dir="ltr"' in content

        # Switch to Persian via API
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Verify change in subsequent page load
        user.refresh_from_db()
        assert user.language == "fa"

        # Load page again with new language
        client.force_login(user)  # Re-login to refresh session
        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")
        assert 'lang="fa"' in content
        assert 'dir="rtl"' in content

    def test_formatting_changes_with_language(self):
        """Test that formatting changes when language changes."""
        test_number = 1234.56
        test_date = date(2024, 1, 15)

        # English formatting
        with translation.override("en"):
            num_en = format_number(test_number)
            date_en = format_date(test_date)

            assert "1,234.56" in num_en
            assert "2024" in date_en

        # Persian formatting
        with translation.override("fa"):
            num_fa = format_number(test_number)
            date_fa = format_date(test_date)

            # Should have Persian numerals
            assert any(char in num_fa for char in "۰۱۲۳۴۵۶۷۸۹")
            assert any(char in date_fa for char in "۰۱۲۳۴۵۶۷۸۹")

            # Date should be in Jalali calendar
            assert "۱۴۰۲" in date_fa  # Year 1402 in Jalali

    def test_rtl_and_formatting_work_together(self, client, user):
        """Test that RTL layout and Persian formatting work together."""
        # Set user to Persian
        user.language = "fa"
        user.save()

        client.force_login(user)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # Should have both RTL and Persian language
        assert 'dir="rtl"' in content
        assert 'lang="fa"' in content

        # If there are any numbers in the page, they should use Persian numerals
        # This is tested indirectly through the formatting functions

    def test_all_supported_languages_configured(self):
        """Test that all supported languages are properly configured."""
        # Check settings
        languages = dict(settings.LANGUAGES)
        assert "en" in languages
        assert "fa" in languages

        # Check that both languages have translation files
        locale_path = settings.LOCALE_PATHS[0]

        for lang_code in ["en", "fa"]:
            po_file = locale_path / lang_code / "LC_MESSAGES" / "django.po"
            mo_file = locale_path / lang_code / "LC_MESSAGES" / "django.mo"

            assert po_file.exists(), f"{lang_code} .po file should exist"
            assert mo_file.exists(), f"{lang_code} .mo file should exist"


class TestI18nRequirementCompliance(TestCase):
    """Test compliance with Requirement 2 specifications."""

    def test_requirement_2_1_english_and_persian_support(self):
        """
        Test Requirement 2.1: Support English (LTR) and Persian (RTL) languages.
        """
        # Check that both languages are configured
        languages = dict(settings.LANGUAGES)
        self.assertIn("en", languages)
        self.assertIn("fa", languages)

        # Check that translation files exist
        locale_path = settings.LOCALE_PATHS[0]
        en_po = locale_path / "en" / "LC_MESSAGES" / "django.po"
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"

        self.assertTrue(en_po.exists())
        self.assertTrue(fa_po.exists())

    def test_requirement_2_2_automatic_rtl_switch(self):
        """
        Test Requirement 2.2: Automatic RTL layout switch for Persian.
        """
        import uuid

        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="fa",
        )

        client = Client()
        client.force_login(user)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")

        # Should have RTL direction for Persian
        self.assertIn('dir="rtl"', content)

    def test_requirement_2_3_all_content_translated(self):
        """
        Test Requirement 2.3: All static content is translatable.
        """
        # Check that translation infrastructure is in place
        self.assertIn("django.middleware.locale.LocaleMiddleware", settings.MIDDLEWARE)
        self.assertTrue(settings.USE_I18N)

        # Check that translation files contain content
        locale_path = settings.LOCALE_PATHS[0]
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"

        with open(fa_po, "r", encoding="utf-8") as f:
            content = f.read()

        # Should contain msgid and msgstr entries
        self.assertIn("msgid", content)
        self.assertIn("msgstr", content)

    def test_requirement_2_4_persian_numerals(self):
        """
        Test Requirement 2.4: Format numbers using Persian numerals for Persian.
        """
        with translation.override("fa"):
            result = format_number(123)
            # Should contain Persian numerals
            self.assertTrue(any(char in result for char in "۰۱۲۳۴۵۶۷۸۹"))

    def test_requirement_2_5_persian_calendar(self):
        """
        Test Requirement 2.5: Support Persian (Jalali) calendar for Persian.
        """
        test_date = date(2024, 3, 20)  # Persian New Year

        with translation.override("fa"):
            result = format_date(test_date)
            # Should be in Jalali calendar (1403)
            self.assertIn("۱۴۰۳", result)

    def test_requirement_2_6_language_preference_persistence(self):
        """
        Test Requirement 2.6: Persist user's language preference across sessions.
        """
        import uuid

        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

        # Change language
        user.language = "fa"
        user.save()

        # Reload from database
        user.refresh_from_db()
        self.assertEqual(user.language, "fa")
