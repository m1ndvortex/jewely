"""
Integration tests for comprehensive audit logging system.

These tests verify end-to-end audit logging functionality with real database operations,
no mocks allowed per Requirement 8.
"""

from django.test import RequestFactory

import pytest

from apps.core.audit_models import AuditLog, DataChangeLog, LoginAttempt
from apps.core.models import Tenant, User


@pytest.mark.django_db
class TestLoginAuditIntegration:
    """Integration tests for login/logout audit logging."""

    def test_successful_login_creates_audit_logs(self):
        """Test that successful login creates both LoginAttempt and AuditLog."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-jewelry",
        )

        user = User.objects.create_user(
            username="shopowner",
            email="owner@testshop.com",
            password="SecurePass123!",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Manually trigger the login signal and log the attempt
        from django.test import RequestFactory

        from apps.core.audit import log_login_attempt

        factory = RequestFactory()
        request = factory.post("/accounts/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        # Log successful login
        log_login_attempt(
            username=user.username,
            user=user,
            success=True,
            request=request,
        )

        # Verify LoginAttempt was created
        login_attempts = LoginAttempt.objects.filter(username="shopowner")
        assert login_attempts.exists()

        attempt = login_attempts.first()
        assert attempt.result == LoginAttempt.RESULT_SUCCESS
        assert attempt.user == user

        # Verify AuditLog was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGIN_SUCCESS,
            user=user,
        )
        assert audit_logs.exists()

    def test_failed_login_creates_audit_logs(self):
        """Test that failed login attempts are logged."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="CorrectPassword123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Manually log failed login attempt
        from django.test import RequestFactory

        from apps.core.audit import log_login_attempt

        factory = RequestFactory()
        request = factory.post("/accounts/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        log_login_attempt(
            username="testuser",
            user=user,
            success=False,
            failure_reason="invalid_password",
            request=request,
        )

        # Verify LoginAttempt was created
        login_attempts = LoginAttempt.objects.filter(username="testuser")
        assert login_attempts.exists()

        attempt = login_attempts.first()
        assert attempt.result == LoginAttempt.RESULT_FAILED_PASSWORD

        # Verify AuditLog was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGIN_FAILED,
        )
        assert audit_logs.exists()

    def test_logout_creates_audit_log(self):
        """Test that logout is logged."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="TestPass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Clear existing logs
        AuditLog.objects.filter(action=AuditLog.ACTION_LOGOUT).delete()

        # Manually log logout
        from django.test import RequestFactory

        from apps.core.audit import log_logout

        factory = RequestFactory()
        request = factory.post("/accounts/logout/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        log_logout(user, request)

        # Verify AuditLog was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGOUT,
            user=user,
        )
        assert audit_logs.exists()


@pytest.mark.django_db
class TestDataModificationAuditIntegration:
    """Integration tests for data modification audit logging."""

    def test_tenant_creation_is_logged(self):
        """Test that tenant creation is automatically logged via signals."""
        # Clear existing logs
        DataChangeLog.objects.all().delete()
        AuditLog.objects.filter(category=AuditLog.CATEGORY_DATA).delete()

        # Create a tenant
        tenant = Tenant.objects.create(
            company_name="New Jewelry Shop",
            slug="new-shop",
            status=Tenant.ACTIVE,
        )

        # Verify DataChangeLog was created
        data_logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_CREATE,
            object_id=str(tenant.id),
        )
        assert data_logs.exists()

        log = data_logs.first()
        assert "New Jewelry Shop" in log.object_repr

        # Verify AuditLog was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE,
            object_id=str(tenant.id),
        )
        assert audit_logs.exists()

    def test_tenant_update_is_logged_with_changes(self):
        """Test that tenant updates are logged with field changes."""
        # Create a tenant
        tenant = Tenant.objects.create(
            company_name="Original Name",
            slug="original-slug",
            status=Tenant.ACTIVE,
        )

        # Clear logs after creation
        DataChangeLog.objects.filter(object_id=str(tenant.id)).delete()
        AuditLog.objects.filter(object_id=str(tenant.id)).delete()

        # Update the tenant
        tenant.company_name = "Updated Name"
        tenant.status = Tenant.SUSPENDED
        tenant.save()

        # Verify DataChangeLog was created with field changes
        data_logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_UPDATE,
            object_id=str(tenant.id),
        )
        assert data_logs.exists()

        log = data_logs.first()
        assert "company_name" in log.field_changes
        assert log.field_changes["company_name"]["old"] == "Original Name"
        assert log.field_changes["company_name"]["new"] == "Updated Name"
        assert "status" in log.field_changes

    def test_tenant_deletion_is_logged(self):
        """Test that tenant deletion is logged."""
        # Create a tenant
        tenant = Tenant.objects.create(
            company_name="To Be Deleted",
            slug="to-delete",
        )

        tenant_id = str(tenant.id)

        # Clear creation logs
        DataChangeLog.objects.filter(object_id=tenant_id).delete()

        # Delete the tenant
        tenant.delete()

        # Verify DataChangeLog was created
        data_logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_DELETE,
            object_id=tenant_id,
        )
        assert data_logs.exists()

    def test_user_creation_is_logged(self):
        """Test that user creation is logged."""
        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        # Clear existing logs
        DataChangeLog.objects.all().delete()

        # Create user
        user = User.objects.create_user(
            username="newemployee",
            email="employee@test.com",
            password="TestPass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Verify DataChangeLog was created
        data_logs = DataChangeLog.objects.filter(
            change_type=DataChangeLog.CHANGE_CREATE,
            object_id=str(user.id),
        )
        assert data_logs.exists()

        log = data_logs.first()
        assert "newemployee" in log.object_repr


@pytest.mark.django_db
class TestAdministrativeActionAuditIntegration:
    """Integration tests for administrative action audit logging."""

    def test_tenant_suspension_workflow(self):
        """Test complete tenant suspension workflow with audit trail."""
        # Create platform admin
        admin = User.objects.create_user(
            username="platformadmin",
            email="admin@platform.com",
            password="AdminPass123!",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Shop to Suspend",
            slug="shop-suspend",
            status=Tenant.ACTIVE,
        )

        # Clear logs
        AuditLog.objects.filter(tenant=tenant).delete()

        # Suspend tenant (simulating admin action)
        from apps.core.audit import log_tenant_action

        request_factory = RequestFactory()
        request = request_factory.post("/admin/tenants/suspend/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Admin Browser"

        tenant.suspend()

        log_tenant_action(
            action="SUSPEND",
            tenant=tenant,
            user=admin,
            old_values={"status": "ACTIVE"},
            new_values={"status": "SUSPENDED"},
            request=request,
        )

        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_TENANT_SUSPEND,
            tenant=tenant,
            user=admin,
        )
        assert audit_logs.exists()

        log = audit_logs.first()
        assert log.severity == AuditLog.SEVERITY_WARNING
        assert log.ip_address == "192.168.1.100"
        assert "Shop to Suspend" in log.description

    def test_user_role_change_workflow(self):
        """Test user role change with audit trail."""
        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        # Create admin and employee
        admin = User.objects.create_user(
            username="shopadmin",
            email="admin@shop.com",
            password="AdminPass123!",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        employee = User.objects.create_user(
            username="employee",
            email="employee@shop.com",
            password="EmpPass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Change role
        from apps.core.audit import log_role_change

        request_factory = RequestFactory()
        request = request_factory.post("/admin/users/change-role/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Chrome"

        old_role = employee.role
        employee.role = User.TENANT_MANAGER
        employee.save()

        log_role_change(
            actor=admin,
            target_user=employee,
            old_role=old_role,
            new_role=employee.role,
            request=request,
        )

        # Verify PermissionAuditLog was created
        from apps.core.models import PermissionAuditLog

        perm_logs = PermissionAuditLog.objects.filter(
            target_user=employee,
            action=PermissionAuditLog.ROLE_CHANGED,
        )
        assert perm_logs.exists()

        log = perm_logs.first()
        assert log.actor == admin
        assert log.old_value == User.TENANT_EMPLOYEE
        assert log.new_value == User.TENANT_MANAGER


@pytest.mark.django_db
class TestSecurityMonitoringIntegration:
    """Integration tests for security monitoring and suspicious activity detection."""

    def test_multiple_failed_login_attempts(self):
        """Test that multiple failed login attempts are logged."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="targetuser",
            email="target@test.com",
            password="CorrectPassword123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Clear existing logs
        LoginAttempt.objects.filter(username="targetuser").delete()

        # Manually log multiple failed attempts
        from django.test import RequestFactory

        from apps.core.audit import log_login_attempt

        factory = RequestFactory()

        for i in range(5):
            request = factory.post("/accounts/login/")
            request.META["REMOTE_ADDR"] = f"192.168.1.{100 + i}"
            request.META["HTTP_USER_AGENT"] = "Test Browser"

            log_login_attempt(
                username="targetuser",
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Verify multiple LoginAttempt records were created
        failed_attempts = LoginAttempt.objects.filter(
            username="targetuser",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
        )
        assert failed_attempts.count() == 5

        # Verify all attempts have IP addresses
        for attempt in failed_attempts:
            assert attempt.ip_address is not None

    def test_security_event_logging(self):
        """Test that security events are properly logged."""
        from apps.core.audit import log_security_event

        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="TestPass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Log a security event
        request_factory = RequestFactory()
        request = request_factory.get("/api/sensitive-data/")
        request.META["REMOTE_ADDR"] = "suspicious.ip.address"
        request.META["HTTP_USER_AGENT"] = "Suspicious Bot"
        request.tenant = tenant

        log_security_event(
            event_type="unauthorized_access",
            description="Attempted access to sensitive endpoint without permission",
            user=user,
            severity="WARNING",
            request=request,
            metadata={
                "endpoint": "/api/sensitive-data/",
                "method": "GET",
            },
        )

        # Verify security audit log was created
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_UNAUTHORIZED_ACCESS,
            user=user,
        )
        assert security_logs.exists()

        log = security_logs.first()
        assert log.severity == AuditLog.SEVERITY_WARNING
        assert log.ip_address == "suspicious.ip.address"
        assert "sensitive endpoint" in log.description.lower()


@pytest.mark.django_db
class TestAuditLogSearchAndFiltering:
    """Integration tests for audit log search and filtering capabilities."""

    def test_filter_logs_by_tenant(self):
        """Test filtering audit logs by tenant."""
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name="Shop 1",
            slug="shop-1",
        )

        tenant2 = Tenant.objects.create(
            company_name="Shop 2",
            slug="shop-2",
        )

        # Create users for each tenant
        user1 = User.objects.create_user(
            username="user1",
            email="user1@shop1.com",
            password="Pass123!",
            tenant=tenant1,
            role=User.TENANT_EMPLOYEE,
        )

        user2 = User.objects.create_user(
            username="user2",
            email="user2@shop2.com",
            password="Pass123!",
            tenant=tenant2,
            role=User.TENANT_EMPLOYEE,
        )

        # Create audit logs for each tenant
        from apps.core.audit import log_logout

        request_factory = RequestFactory()
        request = request_factory.post("/logout/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user1, request)
        log_logout(user2, request)

        # Filter logs by tenant
        tenant1_logs = AuditLog.objects.filter(tenant=tenant1)
        tenant2_logs = AuditLog.objects.filter(tenant=tenant2)

        assert tenant1_logs.exists()
        assert tenant2_logs.exists()
        assert tenant1_logs.count() >= 1
        assert tenant2_logs.count() >= 1

    def test_filter_logs_by_date_range(self):
        """Test filtering audit logs by date range."""
        from datetime import timedelta

        from django.utils import timezone

        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="Pass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create audit log
        from apps.core.audit import log_logout

        request_factory = RequestFactory()
        request = request_factory.post("/logout/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user, request)

        # Filter by date range
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        logs_in_range = AuditLog.objects.filter(
            timestamp__gte=yesterday,
            timestamp__lte=tomorrow,
        )

        assert logs_in_range.exists()

    def test_filter_logs_by_action_type(self):
        """Test filtering audit logs by action type."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="Pass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create different types of audit logs
        from apps.core.audit import log_logout, log_password_change

        request_factory = RequestFactory()
        request = request_factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user, request)
        log_password_change(user, request)

        # Filter by action type
        logout_logs = AuditLog.objects.filter(action=AuditLog.ACTION_LOGOUT)
        password_logs = AuditLog.objects.filter(action=AuditLog.ACTION_PASSWORD_CHANGE)

        assert logout_logs.exists()
        assert password_logs.exists()

    def test_filter_logs_by_ip_address(self):
        """Test filtering audit logs by IP address."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="Pass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create audit logs from different IPs
        from apps.core.audit import log_logout

        request_factory = RequestFactory()

        # Log from IP 1
        request1 = request_factory.post("/logout/")
        request1.META["REMOTE_ADDR"] = "192.168.1.100"
        log_logout(user, request1)

        # Log from IP 2
        request2 = request_factory.post("/logout/")
        request2.META["REMOTE_ADDR"] = "10.0.0.50"
        log_logout(user, request2)

        # Filter by IP address
        ip1_logs = AuditLog.objects.filter(ip_address="192.168.1.100")
        ip2_logs = AuditLog.objects.filter(ip_address="10.0.0.50")

        assert ip1_logs.exists()
        assert ip2_logs.exists()


@pytest.mark.django_db
class TestAuditLogRetentionAndExport:
    """Integration tests for audit log retention and export capabilities."""

    def test_audit_logs_are_queryable(self):
        """Test that audit logs can be queried efficiently."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="Pass123!",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Create multiple audit logs
        from apps.core.audit import log_logout, log_password_change

        request_factory = RequestFactory()
        request = request_factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        for i in range(10):
            log_logout(user, request)

        log_password_change(user, request)

        # Query logs
        all_logs = AuditLog.objects.filter(user=user)
        assert all_logs.count() >= 11

        # Query with ordering
        recent_logs = AuditLog.objects.filter(user=user).order_by("-timestamp")[:5]
        assert recent_logs.count() == 5

        # Query with filtering
        logout_logs = AuditLog.objects.filter(
            user=user,
            action=AuditLog.ACTION_LOGOUT,
        )
        assert logout_logs.count() >= 10

    def test_data_change_logs_preserve_history(self):
        """Test that data change logs preserve complete history."""
        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Original Name",
            slug="original",
        )

        tenant_id = str(tenant.id)

        # Clear creation logs
        DataChangeLog.objects.filter(object_id=tenant_id).delete()

        # Make multiple updates
        tenant.company_name = "First Update"
        tenant.save()

        tenant.company_name = "Second Update"
        tenant.save()

        tenant.company_name = "Third Update"
        tenant.save()

        # Verify all changes are logged
        change_logs = DataChangeLog.objects.filter(
            object_id=tenant_id,
            change_type=DataChangeLog.CHANGE_UPDATE,
        ).order_by("timestamp")

        assert change_logs.count() >= 3

        # Verify field changes are preserved
        for log in change_logs:
            assert "company_name" in log.field_changes
            assert "old" in log.field_changes["company_name"]
            assert "new" in log.field_changes["company_name"]
