"""
Integration tests for theme system (light and dark mode).

These tests verify the complete theme functionality end-to-end without mocks.
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
class TestThemeIntegration(TestCase):
    """Integration tests for theme system - no mocks, real database."""

    def setUp(self):
        """Set up test data with real database."""
        # Create a tenant
        self.tenant, _ = Tenant.objects.get_or_create(
            slug="test-shop-theme-integration",
            defaults={
                "company_name": "Test Jewelry Shop Theme Integration",
                "status": Tenant.ACTIVE,
            },
        )

        # Create test users with different themes
        self.user_light = User.objects.create_user(
            username=f"user_light_{self.id()}",
            email=f"light_{self.id()}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
            theme="light",
        )

        self.user_dark = User.objects.create_user(
            username=f"user_dark_{self.id()}",
            email=f"dark_{self.id()}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_EMPLOYEE,
            theme="dark",
        )

        self.client = Client()

    def test_requirement_3_1_light_and_dark_modes_available(self):
        """
        Requirement 3.1: THE System SHALL provide light mode and dark mode themes
        for all interfaces.
        """
        # Verify theme choices are defined
        theme_choices = dict(User.THEME_CHOICES)
        self.assertIn("light", theme_choices)
        self.assertIn("dark", theme_choices)

        # Verify users can have different themes
        self.assertEqual(self.user_light.theme, "light")
        self.assertEqual(self.user_dark.theme, "dark")

        # Verify theme CSS file exists
        import os

        theme_css_path = os.path.join("static", "css", "theme.css")
        self.assertTrue(
            os.path.exists(theme_css_path), f"Theme CSS file not found at {theme_css_path}"
        )

        # Verify theme CSS contains both light and dark theme definitions
        with open(theme_css_path, "r") as f:
            css_content = f.read()
            self.assertIn(":root", css_content, "Light theme (root) not defined")
            self.assertIn('[data-theme="light"]', css_content, "Light theme not defined")
            self.assertIn('[data-theme="dark"]', css_content, "Dark theme not defined")
            self.assertIn("--color-bg-primary", css_content, "CSS variables not defined")

    def test_requirement_3_2_theme_applied_to_all_pages(self):
        """
        Requirement 3.2: WHEN a user selects a theme, THE System SHALL apply it
        to all pages and components.
        """
        # Test with light theme user
        self.client.force_login(self.user_light)

        # Access dashboard
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-theme="light"')

        # Switch to dark theme
        switch_response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )
        self.assertEqual(switch_response.status_code, 200)

        # Verify theme was updated in database
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "dark")

        # Access dashboard again - should show dark theme
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-theme="dark"')

    def test_requirement_3_3_theme_persists_across_sessions(self):
        """
        Requirement 3.3: THE System SHALL persist the user's theme preference
        across sessions.
        """
        # Set user to dark theme
        self.user_light.theme = "dark"
        self.user_light.save()

        # Simulate new session - create new client
        new_client = Client()
        new_client.force_login(self.user_light)

        # Access any page
        response = new_client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)

        # Verify dark theme is still applied
        self.assertContains(response, 'data-theme="dark"')

        # Verify theme is still dark in database
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "dark")

    def test_requirement_3_5_theme_toggle_accessible_from_all_pages(self):
        """
        Requirement 3.5: THE System SHALL provide a theme toggle accessible
        from all pages.
        """
        self.client.force_login(self.user_light)

        # List of pages to test
        pages_to_test = [
            reverse("core:tenant_dashboard"),
            # Add more pages as they become available
        ]

        for page_url in pages_to_test:
            response = self.client.get(page_url)
            if response.status_code == 200:
                # Verify theme toggle button exists
                self.assertContains(
                    response,
                    "toggleTheme()",
                    msg_prefix=f"Theme toggle not found on {page_url}",
                )
                # Verify theme toggle icons exist
                self.assertContains(
                    response, "icon-sun", msg_prefix=f"Sun icon not found on {page_url}"
                )
                self.assertContains(
                    response, "icon-moon", msg_prefix=f"Moon icon not found on {page_url}"
                )

    def test_theme_switch_api_complete_flow(self):
        """Test complete theme switching flow through API."""
        self.client.force_login(self.user_light)

        # Initial state - light theme
        self.assertEqual(self.user_light.theme, "light")

        # Switch to dark
        response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["message"], "Theme preference updated successfully")

        # Verify in database
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "dark")

        # Switch back to light
        response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "light"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["theme"], "light")

        # Verify in database
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "light")

    def test_theme_switch_validation(self):
        """Test theme switch API validates input correctly."""
        self.client.force_login(self.user_light)

        # Test invalid theme
        response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "invalid"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("Invalid theme choice", data["error"])

        # Verify theme was not changed
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "light")

        # Test missing theme parameter
        response = self.client.post(
            reverse("core:theme_switch"), data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # Verify theme was not changed
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "light")

    def test_theme_switch_requires_authentication(self):
        """Test that theme switch requires authentication."""
        # Try to switch theme without authentication
        response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_multiple_users_independent_themes(self):
        """Test that different users can have different themes independently."""
        # Verify initial states
        self.assertEqual(self.user_light.theme, "light")
        self.assertEqual(self.user_dark.theme, "dark")

        # Login as light user and access dashboard
        self.client.force_login(self.user_light)
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertContains(response, 'data-theme="light"')

        # Logout and login as dark user
        self.client.logout()
        self.client.force_login(self.user_dark)
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertContains(response, 'data-theme="dark"')

        # Switch light user to dark
        self.client.logout()
        self.client.force_login(self.user_light)
        self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )

        # Verify dark user's theme is unchanged
        self.user_dark.refresh_from_db()
        self.assertEqual(self.user_dark.theme, "dark")

        # Verify light user's theme changed
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "dark")

    def test_theme_context_processor(self):
        """Test that theme context processor provides theme to all templates."""
        from django.test import RequestFactory

        from apps.core.context_processors import user_preferences

        factory = RequestFactory()

        # Test with authenticated user
        request = factory.get("/")
        request.user = self.user_light
        context = user_preferences(request)

        self.assertIn("user_theme", context)
        self.assertEqual(context["user_theme"], "light")

        # Test with dark theme user
        request.user = self.user_dark
        context = user_preferences(request)
        self.assertEqual(context["user_theme"], "dark")

        # Test with anonymous user
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        context = user_preferences(request)
        self.assertIn("user_theme", context)
        self.assertEqual(context["user_theme"], "light")  # Default

    def test_theme_in_base_template(self):
        """Test that base template correctly applies theme."""
        self.client.force_login(self.user_light)

        # Test light theme
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Verify data-theme attribute is set
        self.assertIn('data-theme="light"', content)

        # Verify theme CSS is loaded
        self.assertIn("theme.css", content)

        # Verify theme toggle function exists
        self.assertIn("function toggleTheme()", content)

        # Switch to dark theme
        self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )

        # Test dark theme
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Verify data-theme attribute changed
        self.assertIn('data-theme="dark"', content)

    def test_theme_css_variables_defined(self):
        """Test that all required CSS variables are defined in theme.css."""
        import os

        theme_css_path = os.path.join("static", "css", "theme.css")

        with open(theme_css_path, "r") as f:
            css_content = f.read()

        # Required CSS variables for both themes
        required_variables = [
            "--color-bg-primary",
            "--color-bg-secondary",
            "--color-text-primary",
            "--color-text-secondary",
            "--color-border-primary",
            "--color-primary",
            "--color-success",
            "--color-warning",
            "--color-danger",
            "--color-card-bg",
            "--color-input-bg",
            "--color-button-primary-bg",
            "--color-nav-bg",
        ]

        for variable in required_variables:
            self.assertIn(
                variable,
                css_content,
                f"Required CSS variable {variable} not found in theme.css",
            )

    def test_theme_default_value(self):
        """Test that new users get light theme by default."""
        new_user = User.objects.create_user(
            username=f"newuser_{self.id()}",
            email=f"new_{self.id()}@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_EMPLOYEE,
        )

        self.assertEqual(new_user.theme, "light")

    def test_theme_persistence_after_logout_login(self):
        """Test that theme persists after logout and login."""
        # Set user to dark theme
        self.user_light.theme = "dark"
        self.user_light.save()

        # Login
        self.client.force_login(self.user_light)

        # Verify dark theme
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertContains(response, 'data-theme="dark"')

        # Logout
        self.client.logout()

        # Login again
        self.client.force_login(self.user_light)

        # Verify theme is still dark
        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertContains(response, 'data-theme="dark"')

        # Verify in database
        self.user_light.refresh_from_db()
        self.assertEqual(self.user_light.theme, "dark")

    def test_theme_toggle_button_visibility(self):
        """Test that theme toggle button is visible in navigation."""
        self.client.force_login(self.user_light)

        response = self.client.get(reverse("core:tenant_dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Verify theme toggle button exists
        self.assertIn("theme-toggle", content)
        self.assertIn("toggleTheme()", content)

        # Verify both icons exist (one will be hidden via CSS)
        self.assertIn("icon-sun", content)
        self.assertIn("icon-moon", content)

    def test_theme_api_response_format(self):
        """Test that theme switch API returns correct response format."""
        self.client.force_login(self.user_light)

        response = self.client.post(
            reverse("core:theme_switch"),
            data='{"theme": "dark"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify response structure
        self.assertIn("message", data)
        self.assertIn("theme", data)
        self.assertIn("theme_name", data)

        # Verify response values
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["theme_name"], "Dark")
        self.assertEqual(data["message"], "Theme preference updated successfully")
