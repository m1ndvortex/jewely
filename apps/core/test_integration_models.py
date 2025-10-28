"""
Tests for external service integration models.

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

from datetime import timedelta

from django.utils import timezone

import pytest

from apps.core.integration_models import (
    ExternalService,
    IntegrationHealthCheck,
    IntegrationLog,
    OAuth2Token,
)
from apps.core.models import Tenant, User


@pytest.mark.django_db
class TestExternalService:
    """Test ExternalService model."""

    def test_create_external_service(self):
        """Test creating an external service."""
        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create user
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
        )

        # Create external service
        service = ExternalService.objects.create(
            tenant=tenant,
            name="Stripe Payment Gateway",
            service_type=ExternalService.SERVICE_PAYMENT_GATEWAY,
            provider_name="Stripe",
            description="Payment processing",
            auth_type=ExternalService.AUTH_API_KEY,
            api_key="sk_test_123456",
            api_secret="secret_123456",
            base_url="https://api.stripe.com",
            is_active=True,
            created_by=user,
        )

        assert service.id is not None
        assert service.name == "Stripe Payment Gateway"
        assert service.tenant == tenant
        assert service.is_active is True
        assert service.health_status == "UNKNOWN"
        assert service.total_requests == 0
        assert service.failed_requests == 0

    def test_record_request_success(self):
        """Test recording a successful API request."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Record success
        service.record_request_success()

        assert service.total_requests == 1
        assert service.failed_requests == 0
        assert service.consecutive_failures == 0
        assert service.health_status == "HEALTHY"
        assert service.last_used_at is not None

    def test_record_request_failure(self):
        """Test recording a failed API request."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Record failure
        service.record_request_failure("Connection timeout")

        assert service.total_requests == 1
        assert service.failed_requests == 1
        assert service.consecutive_failures == 1
        assert service.last_error_message == "Connection timeout"
        assert service.last_used_at is not None

    def test_health_status_degraded(self):
        """Test health status changes to DEGRADED after 2 failures."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Record 2 failures
        service.record_request_failure("Error 1")
        service.record_request_failure("Error 2")

        assert service.consecutive_failures == 2
        assert service.health_status == "DEGRADED"

    def test_health_status_down(self):
        """Test health status changes to DOWN after 5 failures."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Record 5 failures
        for i in range(5):
            service.record_request_failure(f"Error {i+1}")

        assert service.consecutive_failures == 5
        assert service.health_status == "DOWN"

    def test_get_success_rate(self):
        """Test success rate calculation."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Record 7 successes and 3 failures
        for _ in range(7):
            service.record_request_success()

        for _ in range(3):
            service.record_request_failure("Error")

        success_rate = service.get_success_rate()
        assert success_rate == 70.0  # 7 out of 10


@pytest.mark.django_db
class TestOAuth2Token:
    """Test OAuth2Token model."""

    def test_create_oauth2_token(self):
        """Test creating an OAuth2 token."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        expires_at = timezone.now() + timedelta(hours=1)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            token_type="Bearer",
            expires_at=expires_at,
            scope="read write",
        )

        assert token.id is not None
        assert token.service == service
        assert token.access_token == "access_token_123"
        assert token.refresh_token == "refresh_token_456"
        assert token.is_expired() is False

    def test_is_expired(self):
        """Test token expiration check."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create expired token
        expires_at = timezone.now() - timedelta(hours=1)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="access_token_123",
            expires_at=expires_at,
        )

        assert token.is_expired() is True

    def test_is_expiring_soon(self):
        """Test token expiring soon check."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create token expiring in 5 minutes
        expires_at = timezone.now() + timedelta(minutes=5)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="access_token_123",
            expires_at=expires_at,
        )

        assert token.is_expiring_soon(minutes=10) is True
        assert token.is_expiring_soon(minutes=3) is False


@pytest.mark.django_db
class TestIntegrationHealthCheck:
    """Test IntegrationHealthCheck model."""

    def test_create_health_check(self):
        """Test creating a health check record."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        health_check = IntegrationHealthCheck.objects.create(
            service=service,
            status="SUCCESS",
            response_time_ms=150,
            status_code=200,
        )

        assert health_check.id is not None
        assert health_check.service == service
        assert health_check.status == "SUCCESS"
        assert health_check.response_time_ms == 150
        assert health_check.status_code == 200


@pytest.mark.django_db
class TestIntegrationLog:
    """Test IntegrationLog model."""

    def test_create_integration_log(self):
        """Test creating an integration log entry."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        service = ExternalService.objects.create(
            tenant=tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        log = IntegrationLog.objects.create(
            service=service,
            method="POST",
            endpoint="/api/v1/payments",
            request_headers={"Content-Type": "application/json"},
            request_body='{"amount": 100}',
            response_status_code=200,
            response_body='{"status": "success"}',
            response_time_ms=250,
            success=True,
        )

        assert log.id is not None
        assert log.service == service
        assert log.method == "POST"
        assert log.endpoint == "/api/v1/payments"
        assert log.success is True
        assert log.response_time_ms == 250
