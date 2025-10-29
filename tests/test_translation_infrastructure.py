"""
Tests for translation infrastructure (Task 26.2).

This module tests:
- Translation markers in Python code (gettext, gettext_lazy)
- Translation markers in templates ({% trans %}, {% blocktrans %})
- .po file generation with makemessages
- .mo file compilation with compilemessages
- django-rosetta integration
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ngettext, pgettext

import pytest

from apps.core.translation_utils import (
    BUTTON_LABELS,
    FIELD_LABELS,
    MENU_ITEMS,
    PAYMENT_METHODS,
    STATUS_CHOICES,
    format_currency,
    format_date_range,
    get_confirmation_messages,
    get_error_messages,
    get_item_count_message,
    get_sale_status_message,
    get_success_messages,
    get_welcome_message,
)


class TranslationInfrastructureTest(TestCase):
    """Test translation infrastructure setup."""

    def test_rosetta_installed(self):
        """Test that django-rosetta is installed and configured."""
        self.assertIn("rosetta", settings.INSTALLED_APPS)

    def test_locale_paths_configured(self):
        """Test that locale paths are properly configured."""
        self.assertTrue(hasattr(settings, "LOCALE_PATHS"))
        self.assertTrue(len(settings.LOCALE_PATHS) > 0)

        # Check that locale directory exists
        locale_path = settings.LOCALE_PATHS[0]
        self.assertTrue(locale_path.exists())

    def test_po_files_exist(self):
        """Test that .po files have been generated."""
        locale_path = settings.LOCALE_PATHS[0]

        # Check English .po file
        en_po = locale_path / "en" / "LC_MESSAGES" / "django.po"
        self.assertTrue(en_po.exists(), "English .po file should exist")

        # Check Persian .po file
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"
        self.assertTrue(fa_po.exists(), "Persian .po file should exist")

    def test_mo_files_exist(self):
        """Test that .mo files have been compiled."""
        locale_path = settings.LOCALE_PATHS[0]

        # Check English .mo file
        en_mo = locale_path / "en" / "LC_MESSAGES" / "django.mo"
        self.assertTrue(en_mo.exists(), "English .mo file should exist")

        # Check Persian .mo file
        fa_mo = locale_path / "fa" / "LC_MESSAGES" / "django.mo"
        self.assertTrue(fa_mo.exists(), "Persian .mo file should exist")

    def test_po_file_contains_translations(self):
        """Test that .po files contain extracted strings."""
        locale_path = settings.LOCALE_PATHS[0]
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"

        with open(fa_po, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for some expected strings from translation_utils.py and templates
        self.assertIn("Dashboard", content)
        self.assertIn("Active", content)
        self.assertIn("Inactive", content)
        self.assertIn("Jewelry Shop", content)

    def test_gettext_function_works(self):
        """Test that gettext function works."""
        # Activate English
        translation.activate("en")

        # Test simple translation
        result = _("Dashboard")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "Dashboard")  # No translation yet, returns original

        translation.deactivate()

    def test_gettext_lazy_function_works(self):
        """Test that gettext_lazy function works."""
        # Test lazy translation
        result = _lazy("Dashboard")
        self.assertIsNotNone(result)

        # Convert to string
        str_result = str(result)
        self.assertEqual(str_result, "Dashboard")

    def test_ngettext_function_works(self):
        """Test that ngettext (pluralization) function works."""
        translation.activate("en")

        # Singular
        result = ngettext(
            "You have %(count)d item.",
            "You have %(count)d items.",
            1,
        ) % {"count": 1}
        self.assertIn("1 item", result)

        # Plural
        result = ngettext(
            "You have %(count)d item.",
            "You have %(count)d items.",
            5,
        ) % {"count": 5}
        self.assertIn("5 items", result)

        translation.deactivate()

    def test_pgettext_function_works(self):
        """Test that pgettext (context) function works."""
        translation.activate("en")

        # Test with context
        result = pgettext("sale status", "Completed")
        self.assertEqual(result, "Completed")

        translation.deactivate()


class TranslationUtilsTest(TestCase):
    """Test translation utility functions."""

    def setUp(self):
        """Set up test environment."""
        translation.activate("en")

    def tearDown(self):
        """Clean up test environment."""
        translation.deactivate()

    def test_status_choices_are_lazy(self):
        """Test that status choices use lazy translation."""
        self.assertEqual(len(STATUS_CHOICES), 4)

        # Check that values are lazy strings
        for code, label in STATUS_CHOICES:
            self.assertIsNotNone(label)
            # Convert to string to trigger translation
            str_label = str(label)
            self.assertIsInstance(str_label, str)

    def test_payment_methods_are_lazy(self):
        """Test that payment methods use lazy translation."""
        self.assertEqual(len(PAYMENT_METHODS), 4)

        for code, label in PAYMENT_METHODS:
            self.assertIsNotNone(label)
            str_label = str(label)
            self.assertIsInstance(str_label, str)

    def test_get_welcome_message(self):
        """Test welcome message generation."""
        message = get_welcome_message("John Doe")
        self.assertIn("John Doe", message)
        self.assertIn("Welcome", message)

    def test_get_item_count_message(self):
        """Test item count message with pluralization."""
        # Singular
        message = get_item_count_message(1)
        self.assertIn("1", message)
        self.assertIn("item", message.lower())

        # Plural
        message = get_item_count_message(5)
        self.assertIn("5", message)
        self.assertIn("items", message.lower())

    def test_get_sale_status_message(self):
        """Test sale status message with context."""
        self.assertEqual(get_sale_status_message("completed"), "Completed")
        self.assertEqual(get_sale_status_message("pending"), "Pending")
        self.assertEqual(get_sale_status_message("cancelled"), "Cancelled")

    def test_get_error_messages(self):
        """Test error messages dictionary."""
        errors = get_error_messages()

        self.assertIn("required_field", errors)
        self.assertIn("invalid_email", errors)
        self.assertIn("insufficient_stock", errors)

        # Check that messages are strings
        for key, message in errors.items():
            self.assertIsInstance(message, str)

    def test_get_success_messages(self):
        """Test success messages dictionary."""
        messages = get_success_messages()

        self.assertIn("item_created", messages)
        self.assertIn("sale_completed", messages)

        for key, message in messages.items():
            self.assertIsInstance(message, str)

    def test_get_confirmation_messages(self):
        """Test confirmation messages dictionary."""
        messages = get_confirmation_messages()

        self.assertIn("delete_item", messages)
        self.assertIn("logout", messages)

        for key, message in messages.items():
            self.assertIsInstance(message, str)

    def test_field_labels_are_lazy(self):
        """Test that field labels use lazy translation."""
        self.assertIn("name", FIELD_LABELS)
        self.assertIn("email", FIELD_LABELS)

        # Convert to string
        name_label = str(FIELD_LABELS["name"])
        self.assertEqual(name_label, "Name")

    def test_button_labels_are_lazy(self):
        """Test that button labels use lazy translation."""
        self.assertIn("save", BUTTON_LABELS)
        self.assertIn("cancel", BUTTON_LABELS)

        save_label = str(BUTTON_LABELS["save"])
        self.assertEqual(save_label, "Save")

    def test_menu_items_are_lazy(self):
        """Test that menu items use lazy translation."""
        self.assertIn("dashboard", MENU_ITEMS)
        self.assertIn("inventory", MENU_ITEMS)

        dashboard_label = str(MENU_ITEMS["dashboard"])
        self.assertEqual(dashboard_label, "Dashboard")

    def test_format_date_range(self):
        """Test date range formatting."""
        from datetime import date

        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        result = format_date_range(start, end)
        self.assertIn("2024-01-01", result)
        self.assertIn("2024-12-31", result)
        self.assertIn("to", result)

    def test_format_currency(self):
        """Test currency formatting."""
        result = format_currency(1234.56, "USD")
        self.assertIn("1,234.56", result)
        self.assertIn("USD", result)


class TemplateTranslationTest(TestCase):
    """Test translation in templates."""

    def test_translation_example_template_exists(self):
        """Test that translation example template exists."""
        template_path = Path(settings.BASE_DIR) / "templates" / "core" / "translation_example.html"
        self.assertTrue(template_path.exists())

    def test_translation_example_template_has_trans_tags(self):
        """Test that template contains {% trans %} tags."""
        template_path = Path(settings.BASE_DIR) / "templates" / "core" / "translation_example.html"

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for {% trans %} tags
        self.assertIn("{% trans", content)
        self.assertIn("{% blocktrans", content)
        self.assertIn("{% load i18n %}", content)

    def test_base_template_has_i18n_support(self):
        """Test that base template has i18n support."""
        template_path = Path(settings.BASE_DIR) / "templates" / "base.html"

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for i18n support
        self.assertIn("{% load i18n %}", content)
        self.assertIn("{{ LANGUAGE_CODE }}", content)
        self.assertIn("LANGUAGE_BIDI", content)


class RosettaIntegrationTest(TestCase):
    """Test django-rosetta integration."""

    def test_rosetta_urls_configured(self):
        """Test that rosetta URLs are configured."""
        from django.urls import reverse
        from django.urls.exceptions import NoReverseMatch

        try:
            # Try to reverse rosetta home URL
            url = reverse("rosetta-home")
            self.assertTrue(url.startswith("/rosetta/"))
        except NoReverseMatch:
            # If reverse fails, check URL patterns directly
            from django.urls import get_resolver

            resolver = get_resolver()
            url_patterns = [
                p.pattern._route for p in resolver.url_patterns if hasattr(p.pattern, "_route")
            ]

            # Check if rosetta is in URL patterns
            rosetta_found = any("rosetta" in str(pattern) for pattern in url_patterns)
            self.assertTrue(rosetta_found, "Rosetta URLs should be configured")

    def test_rosetta_requires_authentication(self):
        """Test that rosetta interface requires authentication."""
        # Try to access rosetta without authentication
        response = self.client.get("/rosetta/")

        # Should redirect to login or return 403/404
        self.assertIn(response.status_code, [302, 403, 404])


class TranslationFileStructureTest(TestCase):
    """Test translation file structure."""

    def test_locale_directory_structure(self):
        """Test that locale directory has correct structure."""
        locale_path = settings.LOCALE_PATHS[0]

        # Check English structure
        en_dir = locale_path / "en" / "LC_MESSAGES"
        self.assertTrue(en_dir.exists())

        # Check Persian structure
        fa_dir = locale_path / "fa" / "LC_MESSAGES"
        self.assertTrue(fa_dir.exists())

    def test_po_file_format(self):
        """Test that .po files have correct format."""
        locale_path = settings.LOCALE_PATHS[0]
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"

        with open(fa_po, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for required headers
        self.assertIn("msgid", content)
        self.assertIn("msgstr", content)
        self.assertIn("Content-Type: text/plain; charset=UTF-8", content)

    def test_mo_file_is_binary(self):
        """Test that .mo files are binary."""
        locale_path = settings.LOCALE_PATHS[0]
        fa_mo = locale_path / "fa" / "LC_MESSAGES" / "django.mo"

        # Check that file exists and has size > 0
        self.assertTrue(fa_mo.exists())
        self.assertGreater(fa_mo.stat().st_size, 0)


@pytest.mark.django_db
class TranslationWorkflowTest(TestCase):
    """Test complete translation workflow."""

    def test_translation_workflow(self):
        """Test the complete translation workflow."""
        # 1. Strings are marked for translation in Python code
        test_string = _("Dashboard")
        self.assertIsNotNone(test_string)

        # 2. makemessages extracts strings to .po files
        locale_path = settings.LOCALE_PATHS[0]
        fa_po = locale_path / "fa" / "LC_MESSAGES" / "django.po"
        self.assertTrue(fa_po.exists())

        # 3. .po files contain extracted strings
        with open(fa_po, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Dashboard", content)

        # 4. compilemessages creates .mo files
        fa_mo = locale_path / "fa" / "LC_MESSAGES" / "django.mo"
        self.assertTrue(fa_mo.exists())

        # 5. Translations can be activated
        translation.activate("fa")
        self.assertEqual(translation.get_language(), "fa")
        translation.deactivate()


class TranslationCoverageTest(TestCase):
    """Test translation coverage."""

    def test_translation_utils_module_exists(self):
        """Test that translation_utils module exists."""
        from apps.core import translation_utils

        self.assertIsNotNone(translation_utils)

    def test_translation_example_template_exists(self):
        """Test that translation example template exists."""
        template_path = Path(settings.BASE_DIR) / "templates" / "core" / "translation_example.html"
        self.assertTrue(template_path.exists())

    def test_all_translation_functions_imported(self):
        """Test that all translation functions can be imported."""
        from django.utils.translation import gettext, gettext_lazy, ngettext, pgettext

        self.assertIsNotNone(gettext)
        self.assertIsNotNone(gettext_lazy)
        self.assertIsNotNone(ngettext)
        self.assertIsNotNone(pgettext)
