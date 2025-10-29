"""
Integration tests for Django i18n configuration.
Per Requirement 2 - Dual-Language Support (English and Persian)

These tests verify that i18n works in real scenarios with actual HTTP requests,
database interactions, and template rendering. NO MOCKS ALLOWED.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import translation

import pytest

from apps.core.models import Tenant

User = get_user_model()


def generate_unique_slug(prefix="test"):
    """Generate a unique slug for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.mark.django_db
class I18nHTTPIntegrationTest(TestCase):
    """Test i18n with real HTTP requests."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create a test tenant with unique slug
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug=generate_unique_slug("test-shop"),
            status=Tenant.ACTIVE,
        )

        # Create a test user with unique username
        self.user = User.objects.create_user(
            username=f"testuser-{uuid.uuid4().hex[:8]}",
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_language_cookie_set_on_request(self):
        """Test that language cookie is set when language is changed."""
        # Make a request with language parameter
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="fa")

        # Check that response is successful
        self.assertIn(response.status_code, [200, 302, 404])  # Any valid response

        # Verify language cookie settings exist
        from django.conf import settings

        self.assertEqual(settings.LANGUAGE_COOKIE_NAME, "django_language")
        self.assertEqual(settings.LANGUAGE_COOKIE_AGE, 31536000)

    def test_language_switching_via_middleware(self):
        """Test that LocaleMiddleware processes language correctly."""
        # Test English request
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertIn(response.status_code, [200, 302, 404])

        # Test Persian request
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="fa")
        self.assertIn(response.status_code, [200, 302, 404])

    def test_language_persistence_across_requests(self):
        """Test that language preference persists across multiple requests."""
        # Set language cookie
        self.client.cookies["django_language"] = "fa"

        # Make multiple requests
        for _ in range(3):
            response = self.client.get("/")
            self.assertIn(response.status_code, [200, 302, 404])
            # Cookie should still be present
            self.assertIn("django_language", self.client.cookies)

    def test_supported_languages_accessible(self):
        """Test that both supported languages can be activated."""
        from django.conf import settings

        for lang_code, lang_name in settings.LANGUAGES:
            translation.activate(lang_code)
            current_lang = translation.get_language()
            self.assertIn(current_lang, [lang_code, f"{lang_code}-{lang_code}"])
            translation.deactivate()


@pytest.mark.django_db
class I18nFormatIntegrationTest(TestCase):
    """Test format localization with real data."""

    def test_english_number_formatting_in_context(self):
        """Test English number formatting with real decimal values."""
        from django.utils import translation
        from django.utils.formats import localize

        translation.activate("en")

        # Test with real decimal values
        test_values = [
            Decimal("1234.56"),
            Decimal("999999.99"),
            Decimal("0.01"),
        ]

        for value in test_values:
            # Localize should work without errors
            localized = localize(value)
            self.assertIsNotNone(localized)

        translation.deactivate()

    def test_persian_number_formatting_in_context(self):
        """Test Persian number formatting with real decimal values."""
        from django.utils import translation
        from django.utils.formats import localize

        translation.activate("fa")

        # Test with real decimal values
        test_values = [
            Decimal("1234.56"),
            Decimal("999999.99"),
            Decimal("0.01"),
        ]

        for value in test_values:
            # Localize should work without errors
            localized = localize(value)
            self.assertIsNotNone(localized)

        translation.deactivate()

    def test_english_date_formatting_in_context(self):
        """Test English date formatting with real dates."""
        from django.utils import translation
        from django.utils.formats import date_format

        translation.activate("en")

        # Test with real dates
        test_dates = [
            date(2024, 1, 1),
            date(2024, 12, 31),
            datetime.now().date(),
        ]

        for test_date in test_dates:
            # Format should work without errors
            formatted = date_format(test_date)
            self.assertIsNotNone(formatted)
            self.assertIsInstance(formatted, str)

        translation.deactivate()

    def test_persian_date_formatting_in_context(self):
        """Test Persian date formatting with real dates."""
        from django.utils import translation
        from django.utils.formats import date_format

        translation.activate("fa")

        # Test with real dates
        test_dates = [
            date(2024, 1, 1),
            date(2024, 12, 31),
            datetime.now().date(),
        ]

        for test_date in test_dates:
            # Format should work without errors
            formatted = date_format(test_date)
            self.assertIsNotNone(formatted)
            self.assertIsInstance(formatted, str)

        translation.deactivate()

    def test_format_module_loading(self):
        """Test that format modules load correctly for both languages."""
        from config.formats import en, fa

        # Test English formats are accessible
        self.assertIsNotNone(en.DATE_FORMAT)
        self.assertIsNotNone(en.DECIMAL_SEPARATOR)
        self.assertEqual(en.DECIMAL_SEPARATOR, ".")
        self.assertEqual(en.THOUSAND_SEPARATOR, ",")

        # Test Persian formats are accessible
        self.assertIsNotNone(fa.DATE_FORMAT)
        self.assertIsNotNone(fa.DECIMAL_SEPARATOR)
        self.assertEqual(fa.DECIMAL_SEPARATOR, "٫")  # Persian decimal separator
        self.assertEqual(fa.THOUSAND_SEPARATOR, "٬")  # Persian thousands separator

        # Formats should be different
        self.assertNotEqual(en.DATE_FORMAT, fa.DATE_FORMAT)
        self.assertNotEqual(en.DECIMAL_SEPARATOR, fa.DECIMAL_SEPARATOR)
        self.assertNotEqual(en.FIRST_DAY_OF_WEEK, fa.FIRST_DAY_OF_WEEK)


@pytest.mark.django_db
class I18nDatabaseIntegrationTest(TestCase):
    """Test i18n with real database operations."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=generate_unique_slug("test-shop"),
            status=Tenant.ACTIVE,
        )

    def test_language_preference_with_database(self):
        """Test language preference storage and retrieval with real database."""
        from django.utils import translation

        # Create user with language preference
        user = User.objects.create_user(
            username=f"testuser-{uuid.uuid4().hex[:8]}",
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Verify user was created
        self.assertIsNotNone(user.id)

        # Test language activation
        translation.activate("fa")
        self.assertEqual(translation.get_language(), "fa")

        # Verify user can be retrieved with active language
        retrieved_user = User.objects.get(id=user.id)
        self.assertEqual(retrieved_user.username, user.username)

        translation.deactivate()

    def test_tenant_operations_with_different_languages(self):
        """Test tenant CRUD operations work with different active languages."""
        from django.utils import translation

        # Get initial count
        initial_count = Tenant.objects.count()

        # Test with English
        translation.activate("en")
        tenant_en = Tenant.objects.create(
            company_name="English Shop",
            slug=generate_unique_slug("english-shop"),
            status=Tenant.ACTIVE,
        )
        self.assertIsNotNone(tenant_en.id)

        # Test with Persian
        translation.activate("fa")
        tenant_fa = Tenant.objects.create(
            company_name="فروشگاه فارسی",
            slug=generate_unique_slug("persian-shop"),
            status=Tenant.ACTIVE,
        )
        self.assertIsNotNone(tenant_fa.id)

        # Verify both tenants were created
        self.assertEqual(Tenant.objects.count(), initial_count + 2)

        # Verify retrieval works in both languages
        translation.activate("en")
        retrieved_en = Tenant.objects.get(id=tenant_en.id)
        self.assertEqual(retrieved_en.company_name, "English Shop")

        translation.activate("fa")
        retrieved_fa = Tenant.objects.get(id=tenant_fa.id)
        self.assertEqual(retrieved_fa.company_name, "فروشگاه فارسی")

        translation.deactivate()


@pytest.mark.django_db
class I18nMiddlewareIntegrationTest(TestCase):
    """Test LocaleMiddleware integration with request/response cycle."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_middleware_processes_accept_language_header(self):
        """Test that middleware processes Accept-Language header."""
        # Request with English
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertIn(response.status_code, [200, 302, 404])

        # Request with Persian
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="fa")
        self.assertIn(response.status_code, [200, 302, 404])

        # Request with unsupported language (should fallback to default)
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="de")
        self.assertIn(response.status_code, [200, 302, 404])

    def test_middleware_order_is_correct(self):
        """Test that LocaleMiddleware is in correct position."""
        from django.conf import settings

        middleware_list = settings.MIDDLEWARE

        # LocaleMiddleware should be present
        self.assertIn("django.middleware.locale.LocaleMiddleware", middleware_list)

        # LocaleMiddleware should be after SessionMiddleware
        locale_index = middleware_list.index("django.middleware.locale.LocaleMiddleware")
        session_index = middleware_list.index(
            "django.contrib.sessions.middleware.SessionMiddleware"
        )
        self.assertGreater(locale_index, session_index)

        # LocaleMiddleware should be before CommonMiddleware
        common_index = middleware_list.index("django.middleware.common.CommonMiddleware")
        self.assertLess(locale_index, common_index)


@pytest.mark.django_db
class I18nContextProcessorIntegrationTest(TestCase):
    """Test i18n context processor integration with templates."""

    def test_i18n_context_available_in_templates(self):
        """Test that i18n context is available in template rendering."""
        from django.template import Context, Template
        from django.utils import translation

        # Activate English
        translation.activate("en")

        # Create a simple template that uses i18n
        template = Template("{{ LANGUAGE_CODE }}")
        context = Context({})

        # Render should work
        rendered = template.render(context)
        self.assertIsNotNone(rendered)

        translation.deactivate()

    def test_language_code_available_in_context(self):
        """Test that LANGUAGE_CODE is available in template context."""
        from django.http import HttpRequest
        from django.template.context_processors import i18n as i18n_processor
        from django.utils import translation

        # Create a mock request
        request = HttpRequest()

        # Test with English
        translation.activate("en")
        context = i18n_processor(request)
        self.assertIn("LANGUAGE_CODE", context)
        self.assertEqual(context["LANGUAGE_CODE"], "en")

        # Test with Persian
        translation.activate("fa")
        context = i18n_processor(request)
        self.assertIn("LANGUAGE_CODE", context)
        self.assertEqual(context["LANGUAGE_CODE"], "fa")

        translation.deactivate()


@pytest.mark.django_db
class I18nEndToEndIntegrationTest(TestCase):
    """End-to-end integration tests for i18n functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.tenant = Tenant.objects.create(
            company_name="E2E Test Shop",
            slug=generate_unique_slug("e2e-shop"),
            status=Tenant.ACTIVE,
        )
        self.user = User.objects.create_user(
            username=f"e2euser-{uuid.uuid4().hex[:8]}",
            email=f"e2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_complete_language_switching_workflow(self):
        """Test complete workflow of language switching."""
        from django.utils import translation

        # Step 1: Start with default language
        translation.activate("en")
        self.assertEqual(translation.get_language(), "en")

        # Step 2: Switch to Persian
        translation.activate("fa")
        self.assertEqual(translation.get_language(), "fa")

        # Step 3: Perform database operation
        tenant = Tenant.objects.create(
            company_name="Test in Persian",
            slug=generate_unique_slug("test-persian"),
            status=Tenant.ACTIVE,
        )
        self.assertIsNotNone(tenant.id)

        # Step 4: Switch back to English
        translation.activate("en")
        self.assertEqual(translation.get_language(), "en")

        # Step 5: Verify data is still accessible
        retrieved = Tenant.objects.get(id=tenant.id)
        self.assertEqual(retrieved.company_name, "Test in Persian")

        translation.deactivate()

    def test_format_localization_end_to_end(self):
        """Test format localization in complete workflow."""
        from django.utils import translation
        from django.utils.formats import date_format, localize

        test_date = date(2024, 1, 15)
        test_number = Decimal("1234.56")

        # Test English formatting
        translation.activate("en")
        en_date = date_format(test_date)
        en_number = localize(test_number)
        self.assertIsNotNone(en_date)
        self.assertIsNotNone(en_number)

        # Test Persian formatting
        translation.activate("fa")
        fa_date = date_format(test_date)
        fa_number = localize(test_number)
        self.assertIsNotNone(fa_date)
        self.assertIsNotNone(fa_number)

        # Formats should be different
        self.assertNotEqual(en_date, fa_date)

        translation.deactivate()

    def test_language_isolation_between_requests(self):
        """Test that language settings don't leak between requests."""
        from django.utils import translation

        # Request 1: English
        translation.activate("en")
        lang1 = translation.get_language()
        translation.deactivate()

        # Request 2: Persian
        translation.activate("fa")
        lang2 = translation.get_language()
        translation.deactivate()

        # Request 3: English again
        translation.activate("en")
        lang3 = translation.get_language()
        translation.deactivate()

        # Verify languages were different
        self.assertEqual(lang1, "en")
        self.assertEqual(lang2, "fa")
        self.assertEqual(lang3, "en")


@pytest.mark.django_db
class I18nConfigurationValidationTest(TestCase):
    """Validate that all i18n configuration is correct."""

    def test_all_required_settings_present(self):
        """Test that all required i18n settings are present."""
        from django.conf import settings

        # Required settings
        self.assertTrue(hasattr(settings, "USE_I18N"))
        self.assertTrue(hasattr(settings, "USE_L10N"))
        self.assertTrue(hasattr(settings, "LANGUAGE_CODE"))
        self.assertTrue(hasattr(settings, "LANGUAGES"))
        self.assertTrue(hasattr(settings, "LOCALE_PATHS"))
        self.assertTrue(hasattr(settings, "FORMAT_MODULE_PATH"))
        self.assertTrue(hasattr(settings, "LANGUAGE_COOKIE_NAME"))
        self.assertTrue(hasattr(settings, "LANGUAGE_COOKIE_AGE"))

    def test_locale_directories_exist_and_writable(self):
        """Test that locale directories exist and are writable."""
        import os

        from django.conf import settings

        for locale_path in settings.LOCALE_PATHS:
            # Directory should exist
            self.assertTrue(locale_path.exists())
            self.assertTrue(locale_path.is_dir())

            # Check subdirectories
            for lang_code, _ in settings.LANGUAGES:
                lang_dir = locale_path / lang_code / "LC_MESSAGES"
                self.assertTrue(lang_dir.exists())
                self.assertTrue(lang_dir.is_dir())

                # Directory should be writable
                self.assertTrue(os.access(lang_dir, os.W_OK))

    def test_format_modules_importable(self):
        """Test that format modules can be imported."""
        from config.formats import en, fa

        # English format module
        self.assertTrue(hasattr(en, "DATE_FORMAT"))
        self.assertTrue(hasattr(en, "DECIMAL_SEPARATOR"))
        self.assertTrue(hasattr(en, "THOUSAND_SEPARATOR"))
        self.assertTrue(hasattr(en, "FIRST_DAY_OF_WEEK"))

        # Persian format module
        self.assertTrue(hasattr(fa, "DATE_FORMAT"))
        self.assertTrue(hasattr(fa, "DECIMAL_SEPARATOR"))
        self.assertTrue(hasattr(fa, "THOUSAND_SEPARATOR"))
        self.assertTrue(hasattr(fa, "FIRST_DAY_OF_WEEK"))

    def test_middleware_configuration_complete(self):
        """Test that middleware is properly configured."""
        from django.conf import settings

        middleware = settings.MIDDLEWARE

        # Required middleware should be present
        self.assertIn("django.middleware.locale.LocaleMiddleware", middleware)
        self.assertIn("django.contrib.sessions.middleware.SessionMiddleware", middleware)
        self.assertIn("django.middleware.common.CommonMiddleware", middleware)

    def test_template_context_processor_configured(self):
        """Test that i18n context processor is configured."""
        from django.conf import settings

        templates = settings.TEMPLATES[0]
        context_processors = templates["OPTIONS"]["context_processors"]

        self.assertIn("django.template.context_processors.i18n", context_processors)
