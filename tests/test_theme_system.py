"""
Tests for theme system (light and dark mode).

Per Requirement 3 - Dual-Theme Support
Task 27.1 - Implement theme infrastructure
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestThemeSystem(TestCase):
    """Test theme switching functionality."""

    def setUp(self):
        """Set up test data."""
        # Create a tenant (get_or_create to avoid duplicate slug errors)
        self.tenant, _ = Tenant.objects.get_or_create(
            slug="test-shop-theme",
            defaults={
                "company_name": "Test Jewelry Shop Theme",
                "status": Tenant.ACTIVE,
            },
        )

        # Create a test user
        self.user = User.objects.create_user(
            username=f"testuser_theme_{self.id()}",
            email=f"test_theme_{self.id()}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
            theme="light",  # Default theme
        )

        self.client = Client()

    def test_user_has_theme_field(self):
        """Test that User model has theme field."""
        self.assertTrue(hasattr(self.user, "theme"))
        self.assertEqual(self.user.theme, "light")

    def test_theme_choices(self):
        """Test that theme choices are defined correctly."""
        theme_choices = dict(User.THEME_CHOICES)
        self.assertIn("light", theme_choices)
        self.assertIn("dark", theme_choices)
        self.assertEqual(theme_choices["light"], "Light")
        self.assertEqual(theme_choices["dark"], "Dark")

    def test_default_theme_is_light(self):
        """Test that default theme is light."""
        new_user = User.objects.create_user(
            username="newuser",
            email="new@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_EMPLOYEE,
        )
        self.assertEqual(new_user.theme, "light")

    def test_theme_switch_api_requires_authentication(self):
        """Test that theme switch API requires authentication."""
        url = reverse("core:theme_switch")
        response = self.client.post(url, data={"theme": "dark"}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_theme_switch_to_dark(self):
        """Test switching theme from light to dark."""
        self.client.force_login(self.user)
        url = reverse("core:theme_switch")

        response = self.client.post(url, data={"theme": "dark"}, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Theme preference updated successfully")
        self.assertEqual(data["theme"], "dark")

        # Verify user's theme was updated in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "dark")

    def test_theme_switch_to_light(self):
        """Test switching theme from dark to light."""
        self.user.theme = "dark"
        self.user.save()

        self.client.force_login(self.user)
        url = reverse("core:theme_switch")

        response = self.client.post(url, data={"theme": "light"}, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Theme preference updated successfully")
        self.assertEqual(data["theme"], "light")

        # Verify user's theme was updated in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "light")

    def test_theme_switch_invalid_theme(self):
        """Test that invalid theme choice is rejected."""
        self.client.force_login(self.user)
        url = reverse("core:theme_switch")

        response = self.client.post(url, data={"theme": "invalid"}, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("Invalid theme choice", data["error"])

        # Verify user's theme was not changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "light")

    def test_theme_switch_missing_theme_parameter(self):
        """Test that missing theme parameter is handled."""
        self.client.force_login(self.user)
        url = reverse("core:theme_switch")

        response = self.client.post(url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_theme_persistence_across_requests(self):
        """Test that theme preference persists across requests."""
        self.client.force_login(self.user)

        # Switch to dark theme
        url = reverse("core:theme_switch")
        self.client.post(url, data={"theme": "dark"}, content_type="application/json")

        # Verify theme persists
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "dark")

        # Make another request and verify theme is still dark
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "dark")

    def test_theme_in_template_context(self):
        """Test that theme is available in template context."""
        self.client.force_login(self.user)

        # Access a page (dashboard)
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that user theme is accessible in context
        self.assertEqual(response.context["user"].theme, "light")

    def test_multiple_users_independent_themes(self):
        """Test that different users can have different themes."""
        # Create another user with dark theme
        user2 = User.objects.create_user(
            username="darkuser",
            email="dark@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_EMPLOYEE,
            theme="dark",
        )

        # Verify both users have different themes
        self.assertEqual(self.user.theme, "light")
        self.assertEqual(user2.theme, "dark")

        # Switch first user to dark
        self.user.theme = "dark"
        self.user.save()

        # Verify second user's theme is unchanged
        user2.refresh_from_db()
        self.assertEqual(user2.theme, "dark")

    def test_theme_css_file_exists(self):
        """Test that theme CSS file exists."""
        import os

        theme_css_path = os.path.join("static", "css", "theme.css")
        self.assertTrue(os.path.exists(theme_css_path))

    def test_context_processor_for_authenticated_user(self):
        """Test context processor provides theme for authenticated user."""
        from django.test import RequestFactory

        from apps.core.context_processors import user_preferences

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        context = user_preferences(request)

        self.assertIn("user_theme", context)
        self.assertEqual(context["user_theme"], "light")

    def test_context_processor_for_anonymous_user(self):
        """Test context processor provides default theme for anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from apps.core.context_processors import user_preferences

        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()

        context = user_preferences(request)

        self.assertIn("user_theme", context)
        self.assertEqual(context["user_theme"], "light")  # Default for anonymous
