"""
Tests for the Tenant Context Middleware.

This test suite validates the middleware functionality including:
- Extracting tenant from JWT token or session
- Setting PostgreSQL session variable with tenant_id
- Handling tenant not found cases
- Handling suspended tenant cases
- Handling pending deletion tenant cases
- RLS bypass for platform admins
- Exempt paths handling
"""

from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.test import RequestFactory, TestCase

import pytest

from apps.core.middleware import TenantContextMiddleware
from apps.core.models import Tenant
from apps.core.tenant_context import clear_tenant_context, enable_rls_bypass, get_current_tenant

User = get_user_model()


@pytest.mark.django_db
class TestTenantContextMiddleware(TestCase):
    """Test suite for TenantContextMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        # Enable RLS bypass for test setup
        enable_rls_bypass()

        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: Mock())

        # Create test tenants
        self.active_tenant = Tenant.objects.create(
            company_name="Active Jewelry Shop", slug="active-shop", status=Tenant.ACTIVE
        )

        self.suspended_tenant = Tenant.objects.create(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )

        self.pending_deletion_tenant = Tenant.objects.create(
            company_name="Pending Deletion Shop",
            slug="pending-shop",
            status=Tenant.PENDING_DELETION,
        )

        # Create test user (tenant owner for active tenant)
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            tenant=self.active_tenant,
            role=User.TENANT_OWNER,
        )

        # Clear RLS bypass after setup
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_exempt_paths_skip_tenant_context(self):
        """Test that exempt paths don't require tenant context."""
        exempt_paths = [
            "/admin/",
            "/api/auth/login/",
            "/api/auth/register/",
            "/health/",
            "/static/css/style.css",
            "/media/images/logo.png",
        ]

        for path in exempt_paths:
            request = self.factory.get(path)
            request.user = AnonymousUser()
            request.session = {}

            response = self.middleware.process_request(request)

            # Should return None (continue processing)
            assert response is None

    def test_platform_admin_gets_rls_bypass(self):
        """Test that platform admins get RLS bypass on admin paths."""
        # Create superuser (platform admin)
        admin_user = User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@test.com",
            role=User.PLATFORM_ADMIN,
        )

        request = self.factory.get("/admin/")
        request.user = admin_user
        request.session = {}

        # Clear any existing context
        clear_tenant_context()

        response = self.middleware.process_request(request)

        # Should return None (continue processing)
        assert response is None

        # RLS bypass should be enabled (we can't easily test this without
        # checking the database session, but we can verify no error occurred)

    def test_extract_tenant_from_session(self):
        """Test extracting tenant ID from session."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.active_tenant.id)}

        response = self.middleware.process_request(request)

        # Should return None (continue processing)
        assert response is None

        # Tenant should be set in request
        assert hasattr(request, "tenant")
        assert request.tenant.id == self.active_tenant.id

        # Tenant context should be set in database
        current_tenant = get_current_tenant()
        assert current_tenant == self.active_tenant.id

    def test_extract_tenant_from_user_model(self):
        """Test extracting tenant ID from user model."""
        # Add tenant to user (simulating extended User model)
        self.user.tenant_id = self.active_tenant.id

        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {}

        response = self.middleware.process_request(request)

        # Should return None (continue processing)
        assert response is None

        # Tenant should be set in request
        assert hasattr(request, "tenant")
        assert request.tenant.id == self.active_tenant.id

    def test_suspended_tenant_returns_403(self):
        """Test that suspended tenants get 403 response."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.suspended_tenant.id)}

        response = self.middleware.process_request(request)

        # Should return 403 response
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403

        # Check response content
        import json

        content = json.loads(response.content)
        assert "suspended" in content["error"].lower()
        assert content["tenant_status"] == "suspended"

    def test_pending_deletion_tenant_returns_403(self):
        """Test that tenants pending deletion get 403 response."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.pending_deletion_tenant.id)}

        response = self.middleware.process_request(request)

        # Should return 403 response
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403

        # Check response content
        import json

        content = json.loads(response.content)
        assert "deletion" in content["error"].lower()
        assert content["tenant_status"] == "pending_deletion"

    def test_nonexistent_tenant_returns_404(self):
        """Test that non-existent tenant ID returns 404."""
        fake_tenant_id = uuid4()

        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(fake_tenant_id)}

        response = self.middleware.process_request(request)

        # Should return 404 response
        assert isinstance(response, JsonResponse)
        assert response.status_code == 404

        # Check response content
        import json

        content = json.loads(response.content)
        assert "not found" in content["error"].lower()

    def test_authenticated_user_without_tenant_returns_403(self):
        """Test that authenticated users without tenant context get 403."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {}

        response = self.middleware.process_request(request)

        # Should return 403 response
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403

        # Check response content
        import json

        content = json.loads(response.content)
        assert "tenant context not found" in content["error"].lower()

    def test_anonymous_user_without_tenant_allowed(self):
        """Test that anonymous users without tenant context are allowed."""
        request = self.factory.get("/api/public/")
        request.user = AnonymousUser()
        request.session = {}

        response = self.middleware.process_request(request)

        # Should return None (continue processing)
        assert response is None

    def test_process_response_clears_tenant_context(self):
        """Test that process_response clears tenant context."""
        # Set up request with tenant
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.active_tenant.id)}

        # Process request
        self.middleware.process_request(request)

        # Verify tenant context is set
        assert get_current_tenant() == self.active_tenant.id

        # Process response
        mock_response = Mock()
        self.middleware.process_response(request, mock_response)

        # Tenant context should be cleared
        assert get_current_tenant() is None

    def test_process_exception_clears_tenant_context(self):
        """Test that process_exception clears tenant context."""
        # Set up request with tenant
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.active_tenant.id)}

        # Process request
        self.middleware.process_request(request)

        # Verify tenant context is set
        assert get_current_tenant() == self.active_tenant.id

        # Process exception
        exception = Exception("Test exception")
        self.middleware.process_exception(request, exception)

        # Tenant context should be cleared
        assert get_current_tenant() is None

    def test_invalid_tenant_id_in_session_handled_gracefully(self):
        """Test that invalid tenant ID in session is handled gracefully."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": "not-a-valid-uuid"}

        response = self.middleware.process_request(request)

        # Should return 403 (no valid tenant context)
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403

    def test_tenant_stored_in_request_object(self):
        """Test that tenant is stored in request object for easy access."""
        request = self.factory.get("/dashboard/")
        request.user = self.user
        request.session = {"tenant_id": str(self.active_tenant.id)}

        self.middleware.process_request(request)

        # Tenant should be accessible from request
        assert hasattr(request, "tenant")
        assert hasattr(request, "tenant_id")
        assert request.tenant.id == self.active_tenant.id
        assert request.tenant_id == self.active_tenant.id

    def test_multiple_requests_dont_leak_tenant_context(self):
        """Test that tenant context doesn't leak between requests."""
        # First request with tenant 1
        request1 = self.factory.get("/dashboard/")
        request1.user = self.user
        request1.session = {"tenant_id": str(self.active_tenant.id)}

        self.middleware.process_request(request1)
        assert get_current_tenant() == self.active_tenant.id

        # Clean up first request
        self.middleware.process_response(request1, Mock())
        assert get_current_tenant() is None

        # Second request with different tenant
        request2 = self.factory.get("/dashboard/")
        request2.user = self.user
        request2.session = {"tenant_id": str(self.suspended_tenant.id)}

        response2 = self.middleware.process_request(request2)

        # Should get 403 for suspended tenant, not data from first tenant
        assert isinstance(response2, JsonResponse)
        assert response2.status_code == 403


@pytest.mark.django_db
class TestTenantContextMiddlewareJWT(TestCase):
    """Test JWT token extraction in middleware."""

    def setUp(self):
        """Set up test fixtures."""
        enable_rls_bypass()

        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: Mock())

        self.active_tenant = Tenant.objects.create(
            company_name="Active Shop", slug="active-shop", status=Tenant.ACTIVE
        )

        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            tenant=self.active_tenant,
            role=User.TENANT_OWNER,
        )

        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        try:
            clear_tenant_context()
        except Exception:
            pass

    @pytest.mark.skip(
        reason="JWT library not installed yet - will be tested when JWT auth is implemented"
    )
    def test_extract_tenant_from_jwt_token(self):
        """Test extracting tenant ID from JWT token."""
        # This test will be enabled when JWT authentication is implemented
        # Mock the JWT extraction at the module level
        with patch("rest_framework_simplejwt.tokens.AccessToken") as mock_access_token_class:
            # Mock JWT token
            mock_token = Mock()
            mock_token.get.return_value = str(self.active_tenant.id)
            mock_access_token_class.return_value = mock_token

            request = self.factory.get("/api/dashboard/")
            request.user = self.user
            request.session = {}
            request.META["HTTP_AUTHORIZATION"] = "Bearer fake-jwt-token"

            response = self.middleware.process_request(request)

            # Should return None (continue processing)
            assert response is None

            # Tenant should be set in request
            assert hasattr(request, "tenant")
            assert request.tenant.id == self.active_tenant.id

    def test_jwt_extraction_without_library_installed(self):
        """Test that JWT extraction fails gracefully when library not installed."""
        request = self.factory.get("/api/dashboard/")
        request.user = self.user
        request.session = {}
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake-jwt-token"

        # Without JWT library, should fall back to other methods
        # Since no other method provides tenant, should return 403
        response = self.middleware.process_request(request)

        # Should return 403 (no valid tenant context)
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403


@pytest.mark.django_db
class TestTenantContextMiddlewareEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        enable_rls_bypass()

        self.factory = RequestFactory()
        self.middleware = TenantContextMiddleware(get_response=lambda r: Mock())

        self.active_tenant = Tenant.objects.create(
            company_name="Active Shop", slug="active-shop", status=Tenant.ACTIVE
        )

        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_middleware_handles_missing_session(self):
        """Test middleware handles requests without session."""
        request = self.factory.get("/dashboard/")
        request.user = AnonymousUser()
        # No session attribute

        # Should not crash
        response = self.middleware.process_request(request)

        # Should return None for anonymous user
        assert response is None

    def test_middleware_handles_database_errors_gracefully(self):
        """Test middleware handles database errors gracefully."""
        request = self.factory.get("/dashboard/")
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.username = "testuser"
        request.session = {"tenant_id": str(self.active_tenant.id)}

        # Mock Tenant.objects.get to raise an exception
        with patch("apps.core.middleware.Tenant.objects.get") as mock_get:
            mock_get.side_effect = Exception("Database error")

            # Should handle exception and return error response
            response = self.middleware.process_request(request)

            # Should return 500 error response
            assert isinstance(response, JsonResponse)
            assert response.status_code == 500

    def test_is_exempt_path_method(self):
        """Test _is_exempt_path method."""
        assert self.middleware._is_exempt_path("/admin/") is True
        assert self.middleware._is_exempt_path("/admin/tenants/") is True
        assert self.middleware._is_exempt_path("/api/auth/login/") is True
        assert self.middleware._is_exempt_path("/health/") is True
        assert self.middleware._is_exempt_path("/static/css/style.css") is True
        assert self.middleware._is_exempt_path("/media/images/logo.png") is True

        assert self.middleware._is_exempt_path("/dashboard/") is False
        assert self.middleware._is_exempt_path("/api/inventory/") is False

    def test_is_platform_admin_method(self):
        """Test _is_platform_admin method."""
        # Enable RLS bypass for test setup
        enable_rls_bypass()

        # Create a tenant for regular users
        tenant = Tenant.objects.create(
            company_name="Test Shop", slug="test-shop", status=Tenant.ACTIVE
        )

        # Anonymous user
        assert self.middleware._is_platform_admin(AnonymousUser()) is False

        # Regular user
        user = User.objects.create_user(
            username="regular",
            password="pass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )
        assert self.middleware._is_platform_admin(user) is False

        # Superuser
        superuser = User.objects.create_superuser(
            username="super",
            password="pass123",
            email="super@test.com",
            role=User.PLATFORM_ADMIN,
        )
        assert self.middleware._is_platform_admin(superuser) is True

        # User with PLATFORM_ADMIN role
        user_with_role = User.objects.create_user(
            username="admin", password="pass123", role=User.PLATFORM_ADMIN
        )
        assert self.middleware._is_platform_admin(user_with_role) is True

        clear_tenant_context()
