"""
Tests for Django i18n configuration.
Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from django.conf import settings
from django.test import TestCase
from django.utils import translation

import pytest


class I18nConfigurationTest(TestCase):
    """Test i18n configuration and settings."""

    def test_i18n_enabled(self):
        """Test that internationalization is enabled."""
        self.assertTrue(settings.USE_I18N)
        self.assertTrue(settings.USE_L10N)

    def test_supported_languages(self):
        """Test that English and Persian are configured."""
        languages = dict(settings.LANGUAGES)
        self.assertIn("en", languages)
        self.assertIn("fa", languages)
        self.assertEqual(languages["en"], "English")
        self.assertEqual(languages["fa"], "Persian (فارسی)")

    def test_default_language(self):
        """Test that default language is English."""
        self.assertEqual(settings.LANGUAGE_CODE, "en")

    def test_locale_paths_configured(self):
        """Test that locale paths are configured."""
        self.assertTrue(len(settings.LOCALE_PATHS) > 0)
        locale_path = settings.LOCALE_PATHS[0]
        self.assertTrue(locale_path.exists())

    def test_format_module_path_configured(self):
        """Test that format module path is configured."""
        self.assertIn("config.formats", settings.FORMAT_MODULE_PATH)

    def test_locale_middleware_enabled(self):
        """Test that LocaleMiddleware is in MIDDLEWARE."""
        self.assertIn("django.middleware.locale.LocaleMiddleware", settings.MIDDLEWARE)

    def test_language_cookie_settings(self):
        """Test language cookie configuration."""
        self.assertEqual(settings.LANGUAGE_COOKIE_NAME, "django_language")
        self.assertEqual(settings.LANGUAGE_COOKIE_AGE, 31536000)  # 1 year


class LanguageSwitchingTest(TestCase):
    """Test language switching functionality."""

    def test_english_language_activation(self):
        """Test activating English language."""
        translation.activate("en")
        self.assertEqual(translation.get_language(), "en")

    def test_persian_language_activation(self):
        """Test activating Persian language."""
        translation.activate("fa")
        self.assertEqual(translation.get_language(), "fa")

    def test_language_deactivation(self):
        """Test deactivating language returns to default."""
        translation.activate("fa")
        translation.deactivate()
        # Should return to default language
        current_lang = translation.get_language()
        self.assertIn(current_lang, ["en", "en-us"])


class FormatLocalizationTest(TestCase):
    """Test format localization for English and Persian."""

    def test_english_format_module_exists(self):
        """Test that English format module exists."""
        from config.formats import en

        self.assertTrue(hasattr(en, "DATE_FORMAT"))
        self.assertTrue(hasattr(en, "DECIMAL_SEPARATOR"))
        self.assertTrue(hasattr(en, "THOUSAND_SEPARATOR"))

    def test_persian_format_module_exists(self):
        """Test that Persian format module exists."""
        from config.formats import fa

        self.assertTrue(hasattr(fa, "DATE_FORMAT"))
        self.assertTrue(hasattr(fa, "DECIMAL_SEPARATOR"))
        self.assertTrue(hasattr(fa, "THOUSAND_SEPARATOR"))

    def test_english_number_format(self):
        """Test English number formatting."""
        from config.formats import en

        self.assertEqual(en.DECIMAL_SEPARATOR, ".")
        self.assertEqual(en.THOUSAND_SEPARATOR, ",")
        self.assertEqual(en.NUMBER_GROUPING, 3)

    def test_persian_number_format(self):
        """Test Persian number formatting."""
        from config.formats import fa

        self.assertEqual(fa.DECIMAL_SEPARATOR, "٫")  # Persian decimal separator
        self.assertEqual(fa.THOUSAND_SEPARATOR, "٬")  # Persian thousands separator
        self.assertEqual(fa.NUMBER_GROUPING, 3)

    def test_english_date_format(self):
        """Test English date format configuration."""
        from config.formats import en

        self.assertEqual(en.DATE_FORMAT, "N j, Y")
        self.assertEqual(en.SHORT_DATE_FORMAT, "m/d/Y")

    def test_persian_date_format(self):
        """Test Persian date format configuration."""
        from config.formats import fa

        self.assertEqual(fa.DATE_FORMAT, "Y/m/d")
        self.assertEqual(fa.SHORT_DATE_FORMAT, "Y/m/d")

    def test_english_first_day_of_week(self):
        """Test English first day of week (Sunday)."""
        from config.formats import en

        self.assertEqual(en.FIRST_DAY_OF_WEEK, 0)  # Sunday

    def test_persian_first_day_of_week(self):
        """Test Persian first day of week (Saturday)."""
        from config.formats import fa

        self.assertEqual(fa.FIRST_DAY_OF_WEEK, 6)  # Saturday


class I18nContextProcessorTest(TestCase):
    """Test i18n context processor in templates."""

    def test_i18n_context_processor_enabled(self):
        """Test that i18n context processor is enabled."""
        template_settings = settings.TEMPLATES[0]
        context_processors = template_settings["OPTIONS"]["context_processors"]
        self.assertIn("django.template.context_processors.i18n", context_processors)


@pytest.mark.django_db
class LanguagePreferenceTest(TestCase):
    """Test language preference handling."""

    def test_language_cookie_name(self):
        """Test language cookie name is configured."""
        self.assertEqual(settings.LANGUAGE_COOKIE_NAME, "django_language")

    def test_language_cookie_age(self):
        """Test language cookie age is 1 year."""
        self.assertEqual(settings.LANGUAGE_COOKIE_AGE, 31536000)

    def test_language_cookie_path(self):
        """Test language cookie path is root."""
        self.assertEqual(settings.LANGUAGE_COOKIE_PATH, "/")


class LocalePathTest(TestCase):
    """Test locale directory structure."""

    def test_locale_directory_exists(self):
        """Test that locale directory exists."""
        locale_path = settings.LOCALE_PATHS[0]
        self.assertTrue(locale_path.exists())
        self.assertTrue(locale_path.is_dir())

    def test_english_locale_directory_exists(self):
        """Test that English locale directory exists."""
        locale_path = settings.LOCALE_PATHS[0]
        en_path = locale_path / "en" / "LC_MESSAGES"
        self.assertTrue(en_path.exists())
        self.assertTrue(en_path.is_dir())

    def test_persian_locale_directory_exists(self):
        """Test that Persian locale directory exists."""
        locale_path = settings.LOCALE_PATHS[0]
        fa_path = locale_path / "fa" / "LC_MESSAGES"
        self.assertTrue(fa_path.exists())
        self.assertTrue(fa_path.is_dir())
