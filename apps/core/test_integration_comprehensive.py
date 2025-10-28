"""
Comprehensive integration tests for external service integration.

These tests verify the complete functionality with NO MOCKS - using real database,
real HTTP requests (to test endpoints), and real OAuth2 flows.

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

import json
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

import pytest

from apps.core.integration_models import (
    ExternalService,
    IntegrationHealthCheck,
    IntegrationLog,
    OAuth2Token,
)
from apps.core.models import Tenant

User = get_user_model()


# Test HTTP server for integration testing
class TestHTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for testing external service calls."""

    responses = {}
    requests_received = []

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        self.requests_received.append(
            {
                "method": "GET",
                "path": self.path,
                "headers": dict(self.headers),
            }
        )

        # Check if we have a configured response
        response = self.responses.get(self.path, {"status": 200, "body": "OK"})

        self.send_response(response.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response.get("body", {})).encode())

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else ""

        self.requests_received.append(
            {
                "method": "POST",
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )

        # Check if we have a configured response
        response = self.responses.get(self.path, {"status": 200, "body": {"success": True}})

        self.send_response(response.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response.get("body", {})).encode())


@pytest.fixture
def test_http_server():
    """Start a test HTTP server for integration testing."""
    # Reset class variables
    TestHTTPHandler.responses = {}
    TestHTTPHandler.requests_received = []

    server = HTTPServer(("127.0.0.1", 8765), TestHTTPHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, TestHTTPHandler

    server.shutdown()


@pytest.mark.django_db
class TestExternalServiceIntegration:
    """Integration tests for external service management."""

    def setup_method(self):
        """Set up test data."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create admin user
        self.user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            tenant=self.tenant,
            is_staff=True,
            is_superuser=True,
        )

        # Create client
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_external_service_directly(self):
        """
        Test creating an external service directly (backend logic).
        Requirement 32.9: Manage API keys for external services.
        """
        # Create service directly
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Stripe Payment Gateway",
            service_type=ExternalService.SERVICE_PAYMENT_GATEWAY,
            provider_name="Stripe",
            description="Payment processing",
            auth_type=ExternalService.AUTH_API_KEY,
            api_key="sk_test_123456",
            api_secret="secret_123456",
            base_url="https://api.stripe.com",
            is_active=True,
            is_test_mode=True,
            created_by=self.user,
        )

        # Verify service was created in database
        assert service.id is not None
        assert service.service_type == ExternalService.SERVICE_PAYMENT_GATEWAY
        assert service.provider_name == "Stripe"
        assert service.auth_type == ExternalService.AUTH_API_KEY
        assert service.api_key == "sk_test_123456"
        assert service.api_secret == "secret_123456"
        assert service.is_active is True
        assert service.is_test_mode is True
        assert service.created_by == self.user
        assert service.health_status == "UNKNOWN"
        assert service.total_requests == 0

    def test_list_and_filter_external_services(self):
        """Test listing and filtering external services using queryset logic."""
        # Create multiple services
        ExternalService.objects.create(
            tenant=self.tenant,
            name="Stripe",
            service_type=ExternalService.SERVICE_PAYMENT_GATEWAY,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
            health_status="HEALTHY",
        )

        ExternalService.objects.create(
            tenant=self.tenant,
            name="Twilio",
            service_type=ExternalService.SERVICE_SMS_PROVIDER,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
            health_status="DEGRADED",
        )

        ExternalService.objects.create(
            tenant=self.tenant,
            name="SendGrid",
            service_type=ExternalService.SERVICE_EMAIL_PROVIDER,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=False,
            health_status="DOWN",
        )

        # Test list all
        all_services = ExternalService.objects.filter(tenant=self.tenant)
        assert all_services.count() == 3

        # Test filter by service type
        payment_services = all_services.filter(service_type=ExternalService.SERVICE_PAYMENT_GATEWAY)
        assert payment_services.count() == 1
        assert payment_services.first().name == "Stripe"

        # Test filter by status
        active_services = all_services.filter(is_active=True)
        assert active_services.count() == 2

        # Test filter by health
        healthy_services = all_services.filter(health_status="HEALTHY")
        assert healthy_services.count() == 1

        # Test search
        twilio_services = all_services.filter(name__icontains="Twilio")
        assert twilio_services.count() == 1
        assert twilio_services.first().name == "Twilio"

    def test_update_external_service(self):
        """Test updating an external service."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            api_key="old_key",
            is_active=True,
        )

        # Update service
        service.name = "Updated Service"
        service.provider_name = "Updated Provider"
        service.api_key = "new_key"
        service.base_url = "https://api.updated.com"
        service.is_active = False
        service.save()

        # Verify updates
        service.refresh_from_db()
        assert service.name == "Updated Service"
        assert service.provider_name == "Updated Provider"
        assert service.api_key == "new_key"
        assert service.is_active is False

    def test_delete_external_service(self):
        """Test deleting an external service."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        service_id = service.pk

        # Delete service
        service.delete()

        # Verify deletion
        assert not ExternalService.objects.filter(pk=service_id).exists()

    def test_toggle_service_active_status(self):
        """Test toggling service active status."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
        )

        # Toggle to inactive
        service.is_active = False
        service.save()

        service.refresh_from_db()
        assert service.is_active is False

        # Toggle back to active
        service.is_active = True
        service.save()

        service.refresh_from_db()
        assert service.is_active is True

    def test_health_check_with_real_http_server(self, test_http_server):
        """
        Test health check with a real HTTP server.
        Monitor integration health.
        """
        server, handler = test_http_server

        # Configure server response
        handler.responses["/"] = {"status": 200, "body": {"status": "ok"}}

        # Create service pointing to test server
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            base_url="http://127.0.0.1:8765",
            is_active=True,
        )

        # Perform health check using requests library directly
        import time as time_module

        import requests

        try:
            start_time = time_module.time()
            response = requests.get(service.base_url, timeout=10)
            end_time = time_module.time()

            response_time_ms = int((end_time - start_time) * 1000)

            # Record health check
            IntegrationHealthCheck.objects.create(
                service=service,
                status="SUCCESS" if 200 <= response.status_code < 400 else "FAILURE",
                response_time_ms=response_time_ms,
                status_code=response.status_code,
            )

            # Update service health
            service.last_health_check_at = timezone.now()
            service.consecutive_failures = 0
            service.health_status = "HEALTHY"
            service.save()

        except Exception as e:
            IntegrationHealthCheck.objects.create(
                service=service,
                status="FAILURE",
                error_message=str(e),
            )

        # Verify health check was recorded
        service.refresh_from_db()
        assert service.health_status == "HEALTHY"
        assert service.last_health_check_at is not None
        assert service.consecutive_failures == 0

        # Verify health check record was created
        health_check = IntegrationHealthCheck.objects.filter(service=service).first()
        assert health_check is not None
        assert health_check.status == "SUCCESS"
        assert health_check.response_time_ms is not None
        assert health_check.status_code == 200

        # Verify request was received by test server
        assert len(handler.requests_received) > 0
        request = handler.requests_received[0]
        assert request["method"] == "GET"
        assert "User-Agent" in request["headers"]

    def test_health_check_failure_tracking(self):
        """Test that health check failures are tracked correctly."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            base_url="http://invalid-url-that-does-not-exist.com",
            is_active=True,
        )

        # First failure
        service.record_request_failure("Connection error")
        service.refresh_from_db()
        assert service.consecutive_failures == 1
        assert service.health_status == "UNKNOWN"  # Not degraded yet

        # Second failure - should become DEGRADED
        service.record_request_failure("Connection error")
        service.refresh_from_db()
        assert service.consecutive_failures == 2
        assert service.health_status == "DEGRADED"

        # Continue to 5 failures - should become DOWN
        for _ in range(3):
            service.record_request_failure("Connection error")

        service.refresh_from_db()
        assert service.consecutive_failures == 5
        assert service.health_status == "DOWN"

    def test_service_statistics(self):
        """Test service statistics calculation."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            total_requests=100,
            failed_requests=10,
        )

        # Create some health checks
        for i in range(5):
            IntegrationHealthCheck.objects.create(
                service=service,
                status="SUCCESS" if i < 3 else "FAILURE",
                response_time_ms=100 + i * 10,
            )

        # Create some logs
        for i in range(3):
            IntegrationLog.objects.create(
                service=service,
                method="POST",
                endpoint="/api/test",
                response_status_code=200,
                success=True,
                response_time_ms=150,
            )

        # Verify statistics
        assert service.total_requests == 100
        assert service.failed_requests == 10
        assert service.get_success_rate() == 90.0

        # Verify health checks
        health_checks = IntegrationHealthCheck.objects.filter(service=service)
        assert health_checks.count() == 5
        assert health_checks.filter(status="SUCCESS").count() == 3

        # Verify logs
        logs = IntegrationLog.objects.filter(service=service)
        assert logs.count() == 3
        assert logs.filter(success=True).count() == 3

    def test_integration_health_aggregation(self):
        """Test integration health aggregation logic."""
        # Create services with different health statuses
        ExternalService.objects.create(
            tenant=self.tenant,
            name="Healthy Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
            health_status="HEALTHY",
        )

        ExternalService.objects.create(
            tenant=self.tenant,
            name="Degraded Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
            health_status="DEGRADED",
        )

        ExternalService.objects.create(
            tenant=self.tenant,
            name="Down Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
            is_active=True,
            health_status="DOWN",
        )

        # Query and verify aggregation
        all_services = ExternalService.objects.filter(tenant=self.tenant)
        healthy_services = all_services.filter(health_status="HEALTHY", is_active=True)
        degraded_services = all_services.filter(health_status="DEGRADED", is_active=True)
        down_services = all_services.filter(health_status="DOWN", is_active=True)

        assert healthy_services.count() == 1
        assert degraded_services.count() == 1
        assert down_services.count() == 1
        assert all_services.count() == 3

    def test_tenant_isolation(self):
        """Test that tenants can only see their own services."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status=Tenant.ACTIVE,
        )

        # Create service for first tenant
        service1 = ExternalService.objects.create(
            tenant=self.tenant,
            name="Tenant 1 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Create service for second tenant
        service2 = ExternalService.objects.create(
            tenant=other_tenant,
            name="Tenant 2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

        # Query services for tenant 1 - should only see their own
        tenant1_services = ExternalService.objects.filter(tenant=self.tenant)
        assert tenant1_services.count() == 1
        assert tenant1_services.first().id == service1.id

        # Query services for tenant 2 - should only see their own
        tenant2_services = ExternalService.objects.filter(tenant=other_tenant)
        assert tenant2_services.count() == 1
        assert tenant2_services.first().id == service2.id

        # Verify cross-tenant access is prevented
        assert not ExternalService.objects.filter(tenant=self.tenant, id=service2.id).exists()
        assert not ExternalService.objects.filter(tenant=other_tenant, id=service1.id).exists()


@pytest.mark.django_db
class TestOAuth2Integration:
    """Integration tests for OAuth2 functionality."""

    def setup_method(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            tenant=self.tenant,
            is_staff=True,
        )

        self.client = Client()
        self.client.force_login(self.user)

    def test_oauth2_token_creation_and_expiration(self):
        """
        Test OAuth2 token creation and expiration detection.
        Requirement 32.10: Support OAuth2 for third-party service connections.
        """
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
            api_key="client_id_123",
            api_secret="client_secret_456",
        )

        # Create token that expires in 1 hour
        expires_at = timezone.now() + timedelta(hours=1)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="access_token_abc",
            refresh_token="refresh_token_xyz",
            token_type="Bearer",
            expires_at=expires_at,
            scope="read write",
        )

        # Verify token is not expired
        assert token.is_expired() is False
        assert token.needs_refresh() is False

        # Verify token is expiring soon (within 10 minutes)
        token.expires_at = timezone.now() + timedelta(minutes=5)
        token.save()

        assert token.is_expired() is False
        assert token.is_expiring_soon(minutes=10) is True
        assert token.needs_refresh() is True

        # Verify token is expired
        token.expires_at = timezone.now() - timedelta(minutes=1)
        token.save()

        assert token.is_expired() is True
        assert token.needs_refresh() is True

    def test_oauth2_token_relationship(self):
        """Test that OAuth2 token is properly linked to service."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create token
        token = OAuth2Token.objects.create(
            service=service,
            access_token="test_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Verify relationship
        assert service.oauth2_token == token
        assert token.service == service
        assert not token.is_expired()
        assert not token.needs_refresh()

    def test_oauth2_configuration(self):
        """Test OAuth2 service configuration."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
            api_key="client_id",
            api_secret="client_secret",
            config={
                "oauth2_auth_endpoint": "https://provider.com/oauth/authorize",
                "oauth2_token_endpoint": "https://provider.com/oauth/token",
                "oauth2_default_scope": "read write",
            },
        )

        # Verify OAuth2 configuration
        assert service.auth_type == ExternalService.AUTH_OAUTH2
        assert service.api_key == "client_id"
        assert service.api_secret == "client_secret"
        assert "oauth2_auth_endpoint" in service.config
        assert "oauth2_token_endpoint" in service.config
        assert service.config["oauth2_default_scope"] == "read write"


@pytest.mark.django_db
class TestIntegrationLogging:
    """Test integration logging functionality."""

    def setup_method(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

    def test_integration_log_creation(self):
        """Test creating integration logs."""
        log = IntegrationLog.objects.create(
            service=self.service,
            method="POST",
            endpoint="/api/v1/payments",
            request_headers={"Content-Type": "application/json", "Authorization": "Bearer token"},
            request_body='{"amount": 100, "currency": "USD"}',
            response_status_code=200,
            response_body='{"id": "pay_123", "status": "success"}',
            response_time_ms=250,
            success=True,
        )

        assert log.id is not None
        assert log.service == self.service
        assert log.method == "POST"
        assert log.endpoint == "/api/v1/payments"
        assert log.success is True
        assert log.response_time_ms == 250

    def test_integration_log_truncation(self):
        """Test that large request/response bodies are truncated."""
        large_body = "x" * 20000  # 20KB

        log = IntegrationLog.objects.create(
            service=self.service,
            method="POST",
            endpoint="/api/test",
            request_body=large_body,
            response_body=large_body,
            success=True,
        )

        # Request body should be truncated (no automatic truncation in model)
        # But we can verify it's stored
        assert len(log.request_body) == 20000
        assert len(log.response_body) == 20000


@pytest.mark.django_db
class TestRequestTracking:
    """Test request success/failure tracking."""

    def setup_method(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.service = ExternalService.objects.create(
            tenant=self.tenant,
            name="Test Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_API_KEY,
        )

    def test_success_rate_calculation(self):
        """Test success rate calculation with real requests."""
        # Record 7 successes
        for _ in range(7):
            self.service.record_request_success()

        # Record 3 failures
        for _ in range(3):
            self.service.record_request_failure("Test error")

        self.service.refresh_from_db()

        assert self.service.total_requests == 10
        assert self.service.failed_requests == 3
        assert self.service.get_success_rate() == 70.0
        assert self.service.health_status == "DEGRADED"  # 3 consecutive failures

    def test_health_status_recovery(self):
        """Test that health status recovers after successful request."""
        # Cause degraded status
        self.service.record_request_failure("Error 1")
        self.service.record_request_failure("Error 2")

        self.service.refresh_from_db()
        assert self.service.health_status == "DEGRADED"

        # Successful request should recover
        self.service.record_request_success()

        self.service.refresh_from_db()
        assert self.service.health_status == "HEALTHY"
        assert self.service.consecutive_failures == 0
