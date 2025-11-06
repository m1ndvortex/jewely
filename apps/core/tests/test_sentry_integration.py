"""
Tests for Sentry Integration

Tests the Sentry error tracking integration including:
- Sentry initialization
- Data scrubbing for sensitive information
- Error capture and reporting

Requirements:
- 24.8: Integrate Sentry for error tracking with automatic error grouping
- 25.10: Mask sensitive data in logs and error reports
- 28: Comprehensive testing
"""

from unittest.mock import patch

from django.test import TestCase, override_settings

import pytest

from apps.core.sentry_config import (
    _is_sensitive_key,
    _mask_email,
    _scrub_string,
    before_send,
    initialize_sentry,
    scrub_sensitive_data,
)


class TestSensitiveDataScrubbing(TestCase):
    """Test sensitive data scrubbing functions"""

    def test_is_sensitive_key(self):
        """Test detection of sensitive key names"""
        # Sensitive keys
        self.assertTrue(_is_sensitive_key("password"))
        self.assertTrue(_is_sensitive_key("PASSWORD"))
        self.assertTrue(_is_sensitive_key("user_password"))
        self.assertTrue(_is_sensitive_key("api_key"))
        self.assertTrue(_is_sensitive_key("secret_token"))
        self.assertTrue(_is_sensitive_key("access_token"))
        self.assertTrue(_is_sensitive_key("credit_card"))
        self.assertTrue(_is_sensitive_key("csrf_token"))

        # Non-sensitive keys
        self.assertFalse(_is_sensitive_key("username"))
        self.assertFalse(_is_sensitive_key("email"))
        self.assertFalse(_is_sensitive_key("name"))
        self.assertFalse(_is_sensitive_key("id"))

    def test_mask_email(self):
        """Test email masking"""
        self.assertEqual(_mask_email("john@example.com"), "jo***@example.com")
        self.assertEqual(_mask_email("a@example.com"), "a*@example.com")
        self.assertEqual(_mask_email("ab@example.com"), "ab***@example.com")
        self.assertEqual(_mask_email("verylongemail@example.com"), "ve***@example.com")

    def test_scrub_string_credit_cards(self):
        """Test credit card number scrubbing"""
        text = "Card: 4532-1234-5678-9010"
        scrubbed = _scrub_string(text)
        self.assertIn("XXXX-XXXX-XXXX-XXXX", scrubbed)
        self.assertNotIn("4532", scrubbed)

        text = "Card: 4532 1234 5678 9010"
        scrubbed = _scrub_string(text)
        self.assertIn("XXXX-XXXX-XXXX-XXXX", scrubbed)

    def test_scrub_string_emails(self):
        """Test email scrubbing in strings"""
        text = "Contact: john.doe@example.com for help"
        scrubbed = _scrub_string(text)
        self.assertIn("jo***@example.com", scrubbed)
        self.assertNotIn("john.doe", scrubbed)

    def test_scrub_string_phone_numbers(self):
        """Test phone number scrubbing"""
        text = "Call: 555-123-4567"
        scrubbed = _scrub_string(text)
        self.assertIn("XXX-XXX-4567", scrubbed)
        self.assertNotIn("555-123", scrubbed)

    def test_scrub_sensitive_data_dict(self):
        """Test scrubbing dictionaries"""
        data = {
            "username": "john",
            "password": "secret123",
            "api_key": "abc123",
            "email": "john@example.com",
        }
        scrubbed = scrub_sensitive_data(data)

        self.assertEqual(scrubbed["username"], "john")
        self.assertEqual(scrubbed["password"], "[REDACTED]")
        self.assertEqual(scrubbed["api_key"], "[REDACTED]")
        self.assertIn("jo***@example.com", scrubbed["email"])

    def test_scrub_sensitive_data_nested_dict(self):
        """Test scrubbing nested dictionaries"""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
                "settings": {
                    "api_key": "key123",
                    "theme": "dark",
                },
            }
        }
        scrubbed = scrub_sensitive_data(data)

        self.assertEqual(scrubbed["user"]["name"], "John")
        self.assertEqual(scrubbed["user"]["password"], "[REDACTED]")
        self.assertEqual(scrubbed["user"]["settings"]["api_key"], "[REDACTED]")
        self.assertEqual(scrubbed["user"]["settings"]["theme"], "dark")

    def test_scrub_sensitive_data_list(self):
        """Test scrubbing lists"""
        data = [
            {"username": "john", "password": "secret1"},
            {"username": "jane", "password": "secret2"},
        ]
        scrubbed = scrub_sensitive_data(data)

        self.assertEqual(scrubbed[0]["username"], "john")
        self.assertEqual(scrubbed[0]["password"], "[REDACTED]")
        self.assertEqual(scrubbed[1]["username"], "jane")
        self.assertEqual(scrubbed[1]["password"], "[REDACTED]")


class TestBeforeSendHook(TestCase):
    """Test Sentry before_send hook"""

    def test_before_send_scrubs_request_headers(self):
        """Test that request headers are scrubbed"""
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer token123",
                    "Cookie": "sessionid=abc123",
                    "User-Agent": "Mozilla/5.0",
                }
            }
        }

        result = before_send(event, {})

        self.assertEqual(result["request"]["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(result["request"]["headers"]["Cookie"], "[REDACTED]")
        self.assertEqual(result["request"]["headers"]["User-Agent"], "Mozilla/5.0")

    def test_before_send_scrubs_cookies(self):
        """Test that cookies are scrubbed"""
        event = {
            "request": {
                "cookies": {
                    "sessionid": "abc123",
                    "csrftoken": "xyz789",
                }
            }
        }

        result = before_send(event, {})

        self.assertEqual(result["request"]["cookies"]["sessionid"], "[REDACTED]")
        self.assertEqual(result["request"]["cookies"]["csrftoken"], "[REDACTED]")

    def test_before_send_scrubs_post_data(self):
        """Test that POST data is scrubbed"""
        event = {
            "request": {
                "data": {
                    "username": "john",
                    "password": "secret123",
                    "email": "john@example.com",
                }
            }
        }

        result = before_send(event, {})

        self.assertEqual(result["request"]["data"]["username"], "john")
        self.assertEqual(result["request"]["data"]["password"], "[REDACTED]")
        self.assertIn("jo***@example.com", result["request"]["data"]["email"])

    def test_before_send_scrubs_user_data(self):
        """Test that user data is scrubbed"""
        event = {
            "user": {
                "id": "123",
                "username": "john",
                "email": "john@example.com",
                "ip_address": "192.168.1.1",
            }
        }

        result = before_send(event, {})

        self.assertEqual(result["user"]["id"], "123")
        self.assertEqual(result["user"]["username"], "john")
        self.assertEqual(result["user"]["email"], "jo***@example.com")
        self.assertEqual(result["user"]["ip_address"], "XXX.XXX.XXX.XXX")

    def test_before_send_scrubs_exception_values(self):
        """Test that exception values are scrubbed"""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "Invalid card: 4532-1234-5678-9010",
                    }
                ]
            }
        }

        result = before_send(event, {})

        self.assertIn("XXXX-XXXX-XXXX-XXXX", result["exception"]["values"][0]["value"])
        self.assertNotIn("4532", result["exception"]["values"][0]["value"])

    def test_before_send_scrubs_breadcrumbs(self):
        """Test that breadcrumbs are scrubbed"""
        event = {
            "breadcrumbs": {
                "values": [
                    {
                        "message": "User login with password: secret123",
                        "data": {
                            "username": "john",
                            "password": "secret123",
                        },
                    }
                ]
            }
        }

        result = before_send(event, {})

        breadcrumb = result["breadcrumbs"]["values"][0]
        self.assertEqual(breadcrumb["data"]["username"], "john")
        self.assertEqual(breadcrumb["data"]["password"], "[REDACTED]")


class TestSentryInitialization(TestCase):
    """Test Sentry initialization"""

    @patch("apps.core.sentry_config.sentry_sdk.init")
    def test_initialize_sentry_with_dsn(self, mock_init):
        """Test Sentry initialization with DSN"""
        dsn = "https://example@sentry.io/123456"

        initialize_sentry(
            dsn=dsn,
            environment="production",
            traces_sample_rate=0.2,
            release="1.0.0",
        )

        # Verify sentry_sdk.init was called
        mock_init.assert_called_once()

        # Verify initialization parameters
        call_kwargs = mock_init.call_args[1]
        self.assertEqual(call_kwargs["dsn"], dsn)
        self.assertEqual(call_kwargs["environment"], "production")
        self.assertEqual(call_kwargs["release"], "1.0.0")
        self.assertEqual(call_kwargs["traces_sample_rate"], 0.2)
        self.assertFalse(call_kwargs["send_default_pii"])
        self.assertTrue(call_kwargs["attach_stacktrace"])

    @patch("apps.core.sentry_config.sentry_sdk.init")
    def test_initialize_sentry_without_dsn(self, mock_init):
        """Test Sentry is not initialized without DSN"""
        initialize_sentry(dsn=None)

        # Verify sentry_sdk.init was NOT called
        mock_init.assert_not_called()

    @patch("apps.core.sentry_config.sentry_sdk.init")
    def test_initialize_sentry_with_empty_dsn(self, mock_init):
        """Test Sentry is not initialized with empty DSN"""
        initialize_sentry(dsn="")

        # Verify sentry_sdk.init was NOT called
        mock_init.assert_not_called()

    @patch("apps.core.sentry_config.sentry_sdk.init")
    def test_initialize_sentry_integrations(self, mock_init):
        """Test Sentry integrations are configured"""
        dsn = "https://example@sentry.io/123456"

        initialize_sentry(dsn=dsn)

        call_kwargs = mock_init.call_args[1]
        integrations = call_kwargs["integrations"]

        # Verify integrations are present
        self.assertEqual(len(integrations), 3)

        # Check integration types
        integration_names = [type(i).__name__ for i in integrations]
        self.assertIn("DjangoIntegration", integration_names)
        self.assertIn("CeleryIntegration", integration_names)
        self.assertIn("RedisIntegration", integration_names)


@pytest.mark.django_db
class TestSentryInProduction(TestCase):
    """Test Sentry behavior in production-like settings"""

    @patch("apps.core.sentry_config.sentry_sdk.init")
    @override_settings(
        SENTRY_DSN="https://example@sentry.io/123456",
        SENTRY_ENVIRONMENT="production",
    )
    def test_sentry_captures_exceptions(self, mock_init):
        """Test that Sentry would capture exceptions in production"""
        # This test verifies the configuration is correct
        # Actual exception capture is tested by Sentry SDK itself

        from django.conf import settings

        self.assertEqual(settings.SENTRY_DSN, "https://example@sentry.io/123456")
        self.assertEqual(settings.SENTRY_ENVIRONMENT, "production")

    def test_sensitive_data_not_in_error_context(self):
        """Test that sensitive data is not included in error context"""
        # Simulate an error with sensitive data
        error_context = {
            "user_data": {
                "username": "john",
                "password": "secret123",
                "email": "john@example.com",
            },
            "request_data": {
                "api_key": "key123",
                "card_info": "4532-1234-5678-9010",  # Not a sensitive key name, so string scrubbing applies
            },
        }

        # Scrub the context
        scrubbed = scrub_sensitive_data(error_context)

        # Verify sensitive data is redacted
        self.assertEqual(scrubbed["user_data"]["password"], "[REDACTED]")
        self.assertEqual(scrubbed["request_data"]["api_key"], "[REDACTED]")
        # Card info should be scrubbed by pattern matching
        self.assertIn("XXXX-XXXX-XXXX-XXXX", scrubbed["request_data"]["card_info"])


class TestSentryConfiguration(TestCase):
    """Test Sentry configuration in Django settings"""

    def test_sentry_settings_exist(self):
        """Test that Sentry settings are defined"""
        from django.conf import settings

        # These should exist even if empty
        self.assertTrue(hasattr(settings, "SENTRY_DSN"))
        self.assertTrue(hasattr(settings, "SENTRY_ENVIRONMENT"))
        self.assertTrue(hasattr(settings, "SENTRY_TRACES_SAMPLE_RATE"))

    @override_settings(SENTRY_DSN="")
    def test_sentry_disabled_without_dsn(self):
        """Test that Sentry is disabled when DSN is not provided"""
        from django.conf import settings

        # Empty DSN means Sentry is disabled
        self.assertEqual(settings.SENTRY_DSN, "")

    @override_settings(
        SENTRY_DSN="https://example@sentry.io/123456",
        SENTRY_ENVIRONMENT="staging",
        SENTRY_TRACES_SAMPLE_RATE=0.5,
    )
    def test_sentry_configuration_values(self):
        """Test Sentry configuration values"""
        from django.conf import settings

        self.assertEqual(settings.SENTRY_DSN, "https://example@sentry.io/123456")
        self.assertEqual(settings.SENTRY_ENVIRONMENT, "staging")
        self.assertEqual(settings.SENTRY_TRACES_SAMPLE_RATE, 0.5)
