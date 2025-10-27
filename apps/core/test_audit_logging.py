"""
Tests for comprehensive audit logging system.

Tests cover Requirement 8 - Audit Logs and Security Monitoring.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory

import pytest

from apps.core.audit import (
    log_data_change,
    log_login_attempt,
    log_logout,
    log_mfa_action,
    log_password_change,
    log_password_reset,
    log_security_event,
    log_tenant_action,
)
from apps.core.audit_models import AuditLog, DataChangeLog, LoginAttempt
from apps.core.models import Tenant

User = get_user_model()


@pytest.fixture
def request_factory():
    """Create a request factory for testing."""
    return RequestFactory()


@pytest.fixture
def mock_request(request_factory):
    """Create a mock HTTP request."""
    request = request_factory.get("/test/")
    request.META["REMOTE_ADDR"] = "192.168.1.100"
    request.META["HTTP_USER_AGENT"] = "Test Browser"
    return request


@pytest.mark.django_db
class TestTenantAuditLogging:
    """Test tenant-related audit logging."""

    def test_log_tenant_create(self, mock_request):
        """Test that tenant creation is logged."""
        # Create a platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create a tenant
        tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
        )

        # Log the action
        log_tenant_action(
            action="CREATE",
            tenant=tenant,
            user=admin,
            new_values={"company_name": tenant.company_name, "slug": tenant.slug},
            request=mock_request,
        )

        # Verify audit log was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_TENANT_CREATE,
            tenant=tenant,
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.user == admin
        assert log.category == AuditLog.CATEGORY_ADMIN
        assert log.severity == AuditLog.SEVERITY_INFO
        assert "Test Jewelry Shop" in log.description
        assert log.ip_address == "192.168.1.100"

    def test_log_tenant_suspend(self, mock_request):
        """Test that tenant suspension is logged."""
        admin = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        # Log suspension
        log_tenant_action(
            action="SUSPEND",
            tenant=tenant,
            user=admin,
            request=mock_request,
        )

        # Verify audit log
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_TENANT_SUSPEND,
            tenant=tenant,
        )
        assert logs.count() == 1
        assert logs.first().severity == AuditLog.SEVERITY_WARNING


@pytest.mark.django_db
class TestUserActivityLogging:
    """Test user activity audit logging."""

    def test_log_successful_login(self, mock_request):
        """Test that successful login is logged."""
        # Create a tenant first
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log login
        log_login_attempt(
            username=user.username,
            user=user,
            success=True,
            request=mock_request,
        )

        # Verify LoginAttempt was created
        attempts = LoginAttempt.objects.filter(username=user.username)
        assert attempts.count() == 1

        attempt = attempts.first()
        assert attempt.result == LoginAttempt.RESULT_SUCCESS
        assert attempt.user == user
        assert attempt.ip_address == "192.168.1.100"

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN_SUCCESS)
        assert logs.count() == 1

    def test_log_failed_login(self, mock_request):
        """Test that failed login is logged."""
        # Log failed login (no tenant needed for failed attempts)
        log_login_attempt(
            username="nonexistent",
            user=None,
            success=False,
            failure_reason="user_not_found",
            request=mock_request,
        )

        # Verify LoginAttempt was created
        attempts = LoginAttempt.objects.filter(username="nonexistent")
        assert attempts.count() == 1

        attempt = attempts.first()
        assert attempt.result == LoginAttempt.RESULT_FAILED_USER_NOT_FOUND
        assert attempt.user is None

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN_FAILED)
        assert logs.count() == 1
        assert logs.first().severity == AuditLog.SEVERITY_WARNING

    def test_log_logout(self, mock_request):
        """Test that logout is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log logout
        log_logout(user, mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGOUT,
            user=user,
        )
        assert logs.count() == 1

    def test_log_password_change(self, mock_request):
        """Test that password change is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log password change
        log_password_change(user, mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_PASSWORD_CHANGE,
            user=user,
        )
        assert logs.count() == 1

    def test_log_password_reset(self, mock_request):
        """Test that password reset is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log password reset request
        log_password_reset(user, action="request", request=mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_PASSWORD_RESET_REQUEST,
            user=user,
        )
        assert logs.count() == 1

        # Log password reset completion
        log_password_reset(user, action="complete", request=mock_request)

        # Verify second AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_PASSWORD_RESET_COMPLETE,
            user=user,
        )
        assert logs.count() == 1

    def test_log_mfa_enable(self, mock_request):
        """Test that MFA enable is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log MFA enable
        log_mfa_action(user, action="enable", request=mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_MFA_ENABLE,
            user=user,
        )
        assert logs.count() == 1

    def test_log_mfa_verify(self, mock_request):
        """Test that MFA verification is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log successful MFA verification
        log_mfa_action(user, action="verify", success=True, request=mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_MFA_VERIFY_SUCCESS,
            user=user,
        )
        assert logs.count() == 1

        # Log failed MFA verification
        log_mfa_action(user, action="verify", success=False, request=mock_request)

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_MFA_VERIFY_FAILED,
            user=user,
        )
        assert logs.count() == 1
        assert logs.first().severity == AuditLog.SEVERITY_WARNING


@pytest.mark.django_db
class TestDataChangeLogging:
    """Test data modification audit logging."""

    def test_log_data_create(self, mock_request):
        """Test that data creation is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log data creation
        log_data_change(
            instance=tenant,
            change_type="CREATE",
            user=user,
            request=mock_request,
        )

        # Verify DataChangeLog was created (filter by user to exclude automatic signal logging)
        logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_CREATE,
            object_id=str(tenant.id),
            user=user,
        )
        assert logs.count() == 1

        # Verify AuditLog was created (filter by user)
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE,
            object_id=str(tenant.id),
            user=user,
        )
        assert audit_logs.count() == 1

    def test_log_data_update(self, mock_request):
        """Test that data updates are logged with field changes."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log data update with field changes
        field_changes = {
            "company_name": {
                "old": "Test Shop",
                "new": "Updated Shop",
            },
            "status": {
                "old": "ACTIVE",
                "new": "SUSPENDED",
            },
        }

        log_data_change(
            instance=tenant,
            change_type="UPDATE",
            user=user,
            field_changes=field_changes,
            request=mock_request,
        )

        # Verify DataChangeLog was created
        logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_UPDATE,
            object_id=str(tenant.id),
        )
        assert logs.count() == 1

        log = logs.first()
        assert "company_name" in log.field_changes
        assert log.field_changes["company_name"]["old"] == "Test Shop"
        assert log.field_changes["company_name"]["new"] == "Updated Shop"

    def test_log_data_delete(self, mock_request):
        """Test that data deletion is logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        tenant_id = str(tenant.id)

        # Log data deletion
        log_data_change(
            instance=tenant,
            change_type="DELETE",
            user=user,
            request=mock_request,
        )

        # Verify DataChangeLog was created
        logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_DELETE,
            object_id=tenant_id,
        )
        assert logs.count() == 1


@pytest.mark.django_db
class TestSecurityEventLogging:
    """Test security event audit logging."""

    def test_log_security_breach_attempt(self, mock_request):
        """Test that security breach attempts are logged."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log security event
        log_security_event(
            event_type="breach_attempt",
            description="Attempted SQL injection",
            user=user,
            severity="CRITICAL",
            request=mock_request,
            metadata={"attack_type": "sql_injection", "payload": "' OR '1'='1"},
        )

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_SECURITY_BREACH_ATTEMPT,
            user=user,
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.category == AuditLog.CATEGORY_SECURITY
        assert log.severity == AuditLog.SEVERITY_CRITICAL
        assert "SQL injection" in log.description

    def test_log_rate_limit_exceeded(self, mock_request):
        """Test that rate limit violations are logged."""
        # Log rate limit event
        log_security_event(
            event_type="rate_limit",
            description="Rate limit exceeded for API endpoint",
            severity="WARNING",
            request=mock_request,
            metadata={"endpoint": "/api/products/", "limit": 100, "attempts": 150},
        )

        # Verify AuditLog was created
        logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_SECURITY_RATE_LIMIT_EXCEEDED,
        )
        assert logs.count() == 1
        assert logs.first().severity == AuditLog.SEVERITY_WARNING


@pytest.mark.django_db
class TestAuditLogFiltering:
    """Test audit log filtering and querying."""

    def test_filter_by_category(self, mock_request):
        """Test filtering audit logs by category."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create logs of different categories
        log_login_attempt(user.username, user, True, request=mock_request)
        log_logout(user, mock_request)
        log_security_event("suspicious_activity", "Test event", user=user, request=mock_request)

        # Filter by category
        user_logs = AuditLog.objects.filter(category=AuditLog.CATEGORY_USER)
        security_logs = AuditLog.objects.filter(category=AuditLog.CATEGORY_SECURITY)

        assert user_logs.count() == 2  # login and logout
        assert security_logs.count() == 1

    def test_filter_by_severity(self, mock_request):
        """Test filtering audit logs by severity."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create logs of different severities
        log_logout(user, mock_request)  # INFO
        log_login_attempt("wrong", None, False, "user_not_found", mock_request)  # WARNING
        log_security_event(
            "breach_attempt", "Test", severity="CRITICAL", request=mock_request
        )  # CRITICAL

        # Filter by severity
        info_logs = AuditLog.objects.filter(severity=AuditLog.SEVERITY_INFO)
        warning_logs = AuditLog.objects.filter(severity=AuditLog.SEVERITY_WARNING)
        critical_logs = AuditLog.objects.filter(severity=AuditLog.SEVERITY_CRITICAL)

        assert info_logs.count() >= 1
        assert warning_logs.count() >= 1
        assert critical_logs.count() == 1

    def test_filter_by_user(self, mock_request):
        """Test filtering audit logs by user."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user1 = User.objects.create_user(
            username="user1",
            email="user1@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        user2 = User.objects.create_user(
            username="user2",
            email="user2@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create logs for different users
        log_logout(user1, mock_request)
        log_logout(user2, mock_request)
        log_password_change(user1, mock_request)

        # Filter by user
        user1_logs = AuditLog.objects.filter(user=user1)
        user2_logs = AuditLog.objects.filter(user=user2)

        assert user1_logs.count() == 2
        assert user2_logs.count() == 1


@pytest.mark.django_db
class TestAuditLogRetention:
    """Test audit log data retention and cleanup."""

    def test_audit_logs_are_immutable(self):
        """Test that audit logs cannot be modified through admin."""
        from apps.core.admin import AuditLogAdmin

        admin_instance = AuditLogAdmin(AuditLog, None)

        # Create a regular user (not superuser)
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        regular_user = User.objects.create_user(
            username="regular",
            email="regular@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create a mock request with regular user
        class MockRequest:
            def __init__(self, user):
                self.user = user

        request = MockRequest(regular_user)

        # Verify permissions for regular user
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        # Only superusers can delete
        assert admin_instance.has_delete_permission(request) is False

        # Create a superuser (platform admin)
        superuser = User.objects.create_superuser(
            username="superadmin",
            email="super@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        superuser_request = MockRequest(superuser)

        # Verify superuser can delete
        assert admin_instance.has_delete_permission(superuser_request) is True
