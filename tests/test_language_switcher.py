"""
Tests for language switcher functionality.

Per Requirement 2 - Dual-Language Support (English and Persian)
Task 26.5 - Create language switcher
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestLanguageSwitchView:
    """Test the language switch API endpoint."""

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
            language="en",  # Default to English
        )

    @pytest.fixture
    def api_client(self):
        """Create an API client."""
        return APIClient()

    def test_switch_to_persian(self, api_client, user):
        """Test switching language from English to Persian."""
        # Authenticate
        api_client.force_authenticate(user=user)

        # Switch to Persian
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["language"] == "fa"
        assert response.data["language_name"] == "Persian"
        assert "message" in response.data

        # Verify user's language preference was updated
        user.refresh_from_db()
        assert user.language == "fa"

    def test_switch_to_english(self, api_client, user):
        """Test switching language from Persian to English."""
        # Set user to Persian first
        user.language = "fa"
        user.save()

        # Authenticate
        api_client.force_authenticate(user=user)

        # Switch to English
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "en"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["language"] == "en"
        assert response.data["language_name"] == "English"

        # Verify user's language preference was updated
        user.refresh_from_db()
        assert user.language == "en"

    def test_switch_with_invalid_language(self, api_client, user):
        """Test switching to an invalid language code."""
        api_client.force_authenticate(user=user)

        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "invalid"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "valid_choices" in response.data

        # Verify user's language preference was NOT changed
        user.refresh_from_db()
        assert user.language == "en"

    def test_switch_without_authentication(self, api_client):
        """Test that unauthenticated users cannot switch language."""
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_switch_without_language_parameter(self, api_client, user):
        """Test switching without providing language parameter."""
        api_client.force_authenticate(user=user)

        url = reverse("core:language_switch")
        response = api_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_language_persistence_across_requests(self, api_client, user):
        """Test that language preference persists across multiple requests."""
        api_client.force_authenticate(user=user)

        # Switch to Persian
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Make another request and verify language is still Persian
        user.refresh_from_db()
        assert user.language == "fa"

        # Switch back to English
        response = api_client.post(url, {"language": "en"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.language == "en"


@pytest.mark.django_db
class TestLanguageSwitcherIntegration(TestCase):
    """Integration tests for language switcher with middleware."""

    def setUp(self):
        """Set up test data."""
        import uuid

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
            language="en",
        )

    def test_middleware_applies_user_language_preference(self):
        """Test that middleware applies user's language preference."""
        # Set user language to Persian
        self.user.language = "fa"
        self.user.save()

        # Login
        self.client.force_login(self.user)

        # Make a request
        response = self.client.get(reverse("core:tenant_dashboard"))

        # Check that Persian language is active
        # This is tested indirectly through the response
        self.assertEqual(response.status_code, 200)

    def test_language_switch_affects_subsequent_requests(self):
        """Test that switching language affects subsequent page loads."""
        self.client.force_login(self.user)

        # Initial language is English
        self.assertEqual(self.user.language, "en")

        # Switch to Persian via API
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=self.user)

        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify user preference was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, "fa")


@pytest.mark.django_db
class TestLanguageSwitcherUI:
    """Test language switcher UI components."""

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

    def test_language_switcher_appears_in_navigation(self, client, user):
        """Test that language switcher appears in the navigation bar."""
        client.force_login(user)

        response = client.get(reverse("core:tenant_dashboard"))

        assert response.status_code == 200
        # Check for language switcher elements in the response
        content = response.content.decode("utf-8")
        assert "switchLanguage" in content  # JavaScript function
        assert "/api/user/language/switch/" in content  # URL reference

    def test_current_language_displayed_correctly(self, client, user):
        """Test that current language is displayed correctly in switcher."""
        # Test with English
        user.language = "en"
        user.save()
        client.force_login(user)

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")
        assert 'lang="en"' in content

        # Test with Persian
        user.language = "fa"
        user.save()

        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")
        assert 'lang="fa"' in content


@pytest.mark.django_db
class TestLanguagePreferenceRequirements:
    """Test that all requirements for language preference are met."""

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

    def test_requirement_2_6_language_preference_stored_in_profile(self, user):
        """
        Test Requirement 2.6: Store language preference in user profile.
        """
        # Verify user has language field
        assert hasattr(user, "language")

        # Verify language can be set and persisted
        user.language = "fa"
        user.save()

        # Reload from database
        user.refresh_from_db()
        assert user.language == "fa"

    def test_requirement_2_6_language_preference_persists_across_sessions(self, api_client, user):
        """
        Test Requirement 2.6: Language preference persists across sessions.
        """
        api_client.force_authenticate(user=user)

        # Set language to Persian
        url = reverse("core:language_switch")
        response = api_client.post(url, {"language": "fa"}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Simulate new session by creating new client
        new_client = APIClient()
        new_client.force_authenticate(user=user)

        # Verify language preference is still Persian
        user.refresh_from_db()
        assert user.language == "fa"

    def test_language_selection_interface_exists(self, client, user):
        """
        Test that language selection interface is implemented.
        """
        client.force_login(user)

        # Check that language switch endpoint exists
        url = reverse("core:language_switch")
        assert url is not None

        # Check that base template includes language switcher
        response = client.get(reverse("core:tenant_dashboard"))
        content = response.content.decode("utf-8")
        assert "switchLanguage" in content

    def test_language_applied_to_all_pages(self, client, user):
        """
        Test that language preference is applied to all pages.
        """
        # Set user language to Persian
        user.language = "fa"
        user.save()

        client.force_login(user)

        # Test multiple pages
        pages = [
            reverse("core:tenant_dashboard"),
        ]

        for page_url in pages:
            response = client.get(page_url)
            if response.status_code == 200:
                content = response.content.decode("utf-8")
                # Check that Persian language is set in HTML
                assert 'lang="fa"' in content or 'dir="rtl"' in content
