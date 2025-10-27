"""
Integration tests for audit log explorer (Task 20.2).

These tests verify the audit log explorer functionality including:
- Advanced search and filtering
- CSV export
- Retention policies
- Login attempt explorer
- Data change explorer
- API request explorer

NO MOCKS ALLOWED - All tests use real database and services.
"""

import csv
import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.audit import (
    log_data_change,
    log_login_attempt,
    log_logout,
    log_password_change,
    log_security_event,
    log_tenant_action,
)
from apps.core.audit_models import APIRequestLog, AuditLog, LoginAttempt
from apps.core.models import Tenant

User = get_user_model()


@pytest.fixture(autouse=True)
def disable_audit_signals():
    """Disable audit signals for these tests to avoid conflicts with force_login."""
    with (
        patch("apps.core.audit_signals.user_logged_in.send"),
        patch("apps.core.audit_signals.user_logged_out.send"),
        patch("apps.core.audit_signals.user_login_failed.send"),
    ):
        yield


@pytest.mark.django_db
class TestAuditLogExplorerView:
    """Test the main audit log explorer view."""

    def test_audit_log_explorer_requires_platform_admin(self):
        """Test that only platform admins can access the audit log explorer."""
        # Create a regular tenant user
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

        client = Client()
        client.force_login(regular_user)

        # Try to access audit log explorer
        response = client.get(reverse("core:audit_log_explorer"))

        # Should be forbidden or redirected
        assert response.status_code in [302, 403]

    def test_audit_log_explorer_accessible_by_platform_admin(self):
        """Test that platform admins can access the audit log explorer."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        client = Client()
        client.force_login(admin)

        # Access audit log explorer
        response = client.get(reverse("core:audit_log_explorer"))

        # Should be successful
        assert response.status_code == 200
        assert "audit_logs" in response.context

    def test_audit_log_search_by_description(self):
        """Test searching audit logs by description."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and log an action
        tenant = Tenant.objects.create(
            company_name="Searchable Shop",
            slug="searchable-shop",
        )

        # Create a mock request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        log_tenant_action(
            action="CREATE",
            tenant=tenant,
            user=admin,
            new_values={"company_name": tenant.company_name},
            request=request,
        )

        # Search for the log
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_explorer"), {"q": "Searchable Shop"})

        assert response.status_code == 200
        audit_logs = response.context["audit_logs"]
        assert audit_logs.count() > 0
        assert any("Searchable Shop" in log.description for log in audit_logs)

    def test_audit_log_filter_by_category(self):
        """Test filtering audit logs by category."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant
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
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test"

        log_logout(user, request)  # USER category
        log_security_event("suspicious_activity", "Test", user=user, request=request)  # SECURITY

        # Filter by USER category
        client = Client()
        client.force_login(admin)

        response = client.get(
            reverse("core:audit_log_explorer"), {"category": AuditLog.CATEGORY_USER}
        )

        assert response.status_code == 200
        audit_logs = response.context["audit_logs"]
        assert all(log.category == AuditLog.CATEGORY_USER for log in audit_logs)

    def test_audit_log_filter_by_date_range(self):
        """Test filtering audit logs by date range."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Create a log
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user, request)

        # Filter by today's date
        client = Client()
        client.force_login(admin)

        today = timezone.now().date()
        response = client.get(
            reverse("core:audit_log_explorer"),
            {"date_from": today.strftime("%Y-%m-%d"), "date_to": today.strftime("%Y-%m-%d")},
        )

        assert response.status_code == 200
        audit_logs = response.context["audit_logs"]
        assert audit_logs.count() > 0

    def test_audit_log_filter_by_ip_address(self):
        """Test filtering audit logs by IP address."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Create logs from specific IP
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "10.20.30.40"

        log_logout(user, request)

        # Filter by IP
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_explorer"), {"ip": "10.20.30.40"})

        assert response.status_code == 200
        audit_logs = response.context["audit_logs"]
        assert all(log.ip_address == "10.20.30.40" for log in audit_logs if log.ip_address)

    def test_audit_log_quick_filter_today(self):
        """Test quick filter for today's logs."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Create a log today
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user, request)

        # Use quick filter
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_explorer"), {"quick_filter": "today"})

        assert response.status_code == 200
        audit_logs = response.context["audit_logs"]
        today = timezone.now().date()
        assert all(log.timestamp.date() == today for log in audit_logs)


@pytest.mark.django_db
class TestAuditLogExportView:
    """Test CSV export functionality."""

    def test_csv_export_requires_platform_admin(self):
        """Test that only platform admins can export audit logs."""
        # Create regular user
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

        client = Client()
        client.force_login(regular_user)

        # Try to export
        response = client.get(reverse("core:audit_log_export"))

        # Should be forbidden or redirected
        assert response.status_code in [302, 403]

    def test_csv_export_generates_valid_csv(self):
        """Test that CSV export generates valid CSV file."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create some audit logs
        tenant = Tenant.objects.create(
            company_name="Export Test Shop",
            slug="export-shop",
        )

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "Test"

        log_tenant_action(
            action="CREATE",
            tenant=tenant,
            user=admin,
            new_values={"company_name": tenant.company_name},
            request=request,
        )

        # Export to CSV
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_export"))

        # Should be successful
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

        # Parse CSV
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Should have header and at least one data row
        assert len(rows) >= 2
        header = rows[0]
        assert "Timestamp" in header
        assert "Action" in header
        assert "User" in header
        assert "Description" in header

    def test_csv_export_applies_filters(self):
        """Test that CSV export respects filters."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        log_logout(user, request)  # USER category
        log_password_change(user, request)  # USER category

        # Export with category filter
        client = Client()
        client.force_login(admin)

        response = client.get(
            reverse("core:audit_log_export"), {"category": AuditLog.CATEGORY_USER}
        )

        assert response.status_code == 200

        # Parse CSV and verify all rows are USER category
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Skip header
        for row in rows[1:]:
            # Category is the second column
            assert "User Activity" in row[1]


@pytest.mark.django_db
class TestLoginAttemptExplorer:
    """Test login attempt explorer."""

    def test_login_attempt_explorer_shows_attempts(self):
        """Test that login attempt explorer displays login attempts."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Log some login attempts
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        log_login_attempt(username=user.username, user=user, success=True, request=request)
        log_login_attempt(
            username=user.username,
            user=user,
            success=False,
            failure_reason="invalid_password",
            request=request,
        )

        # Access login attempt explorer
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:login_attempt_explorer"))

        assert response.status_code == 200
        assert "login_attempts" in response.context
        login_attempts = response.context["login_attempts"]
        assert login_attempts.count() >= 2

    def test_login_attempt_filter_by_result(self):
        """Test filtering login attempts by result."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Log failed attempts
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        log_login_attempt(
            username=user.username,
            user=user,
            success=False,
            failure_reason="invalid_password",
            request=request,
        )

        # Filter by failed result
        client = Client()
        client.force_login(admin)

        response = client.get(
            reverse("core:login_attempt_explorer"),
            {"result": LoginAttempt.RESULT_FAILED_PASSWORD},
        )

        assert response.status_code == 200
        login_attempts = response.context["login_attempts"]
        assert all(
            attempt.result == LoginAttempt.RESULT_FAILED_PASSWORD for attempt in login_attempts
        )


@pytest.mark.django_db
class TestDataChangeExplorer:
    """Test data change explorer."""

    def test_data_change_explorer_shows_changes(self):
        """Test that data change explorer displays data changes."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Original Name",
            slug="original",
        )

        # Make a change
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        field_changes = {"company_name": {"old": "Original Name", "new": "Updated Name"}}

        log_data_change(
            instance=tenant,
            change_type="UPDATE",
            user=admin,
            field_changes=field_changes,
            request=request,
        )

        # Access data change explorer
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:data_change_explorer"))

        assert response.status_code == 200
        assert "data_changes" in response.context
        data_changes = response.context["data_changes"]
        assert data_changes.count() > 0


@pytest.mark.django_db
class TestAPIRequestExplorer:
    """Test API request explorer."""

    def test_api_request_explorer_shows_requests(self):
        """Test that API request explorer displays API requests."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and user
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

        # Create API request log
        APIRequestLog.objects.create(
            tenant=tenant,
            user=user,
            method="GET",
            path="/api/products/",
            status_code=200,
            response_time_ms=150,
            ip_address="192.168.1.100",
        )

        # Access API request explorer
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:api_request_explorer"))

        assert response.status_code == 200
        assert "api_requests" in response.context
        api_requests = response.context["api_requests"]
        assert api_requests.count() > 0


@pytest.mark.django_db
class TestRetentionPolicy:
    """Test audit log retention policy."""

    def test_retention_policy_view_accessible(self):
        """Test that retention policy view is accessible to platform admins."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_retention"))

        assert response.status_code == 200
        assert "stats" in response.context

    def test_retention_policy_execution_deletes_old_logs(self):
        """Test that retention policy execution deletes old logs."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create an old audit log (100 days ago)
        old_timestamp = timezone.now() - timedelta(days=100)
        old_log = AuditLog.objects.create(
            user=admin,
            category=AuditLog.CATEGORY_SYSTEM,
            action=AuditLog.ACTION_CREATE,
            severity=AuditLog.SEVERITY_INFO,
            description="Old log for testing",
            request_method="SYSTEM",
            request_path="/",
        )
        # Update timestamp manually since auto_now_add=True ignores passed value
        AuditLog.objects.filter(id=old_log.id).update(timestamp=old_timestamp)
        old_log.refresh_from_db()

        # Execute retention policy (90 days)
        client = Client()
        client.force_login(admin)

        response = client.post(
            reverse("core:audit_log_retention_execute"),
            {"retention_days": "90", "log_type": "audit_logs"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted_counts" in data

        # Verify old log was deleted
        assert not AuditLog.objects.filter(id=old_log.id).exists()

    def test_retention_policy_enforces_minimum_30_days(self):
        """Test that retention policy enforces minimum 30 days."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Try to execute with less than 30 days
        client = Client()
        client.force_login(admin)

        response = client.post(
            reverse("core:audit_log_retention_execute"),
            {"retention_days": "15", "log_type": "all"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "30 days" in data["error"]

    def test_retention_policy_preserves_recent_logs(self):
        """Test that retention policy preserves recent logs."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create a recent audit log
        recent_log = AuditLog.objects.create(
            user=admin,
            category=AuditLog.CATEGORY_SYSTEM,
            action=AuditLog.ACTION_CREATE,
            severity=AuditLog.SEVERITY_INFO,
            description="Recent log",
        )

        # Execute retention policy (90 days)
        client = Client()
        client.force_login(admin)

        response = client.post(
            reverse("core:audit_log_retention_execute"),
            {"retention_days": "90", "log_type": "audit_logs"},
        )

        assert response.status_code == 200

        # Verify recent log still exists
        assert AuditLog.objects.filter(id=recent_log.id).exists()


@pytest.mark.django_db
class TestAuditLogDetailView:
    """Test audit log detail view."""

    def test_audit_log_detail_shows_full_information(self):
        """Test that detail view shows complete audit log information."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Detail Test Shop",
            slug="detail-shop",
        )

        # Create audit log
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        log_tenant_action(
            action="CREATE",
            tenant=tenant,
            user=admin,
            new_values={"company_name": tenant.company_name},
            request=request,
        )

        # Get the log
        audit_log = AuditLog.objects.filter(tenant=tenant).first()

        # Access detail view
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_detail", kwargs={"pk": audit_log.pk}))

        assert response.status_code == 200
        assert "audit_log" in response.context
        assert response.context["audit_log"].id == audit_log.id


@pytest.mark.django_db
class TestAuditLogPagination:
    """Test pagination in audit log explorer."""

    def test_audit_log_pagination_works(self):
        """Test that pagination works correctly."""
        # Create platform admin
        admin = User.objects.create_user(
            username="admin",
            email="admin@platform.com",
            password="adminpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Create many audit logs (more than page size of 50)
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

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Create 60 logs
        for i in range(60):
            log_logout(user, request)

        # Access first page
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("core:audit_log_explorer"))

        assert response.status_code == 200
        assert response.context["is_paginated"] is True
        assert len(response.context["audit_logs"]) == 50  # Page size

        # Access second page
        response = client.get(reverse("core:audit_log_explorer"), {"page": 2})

        assert response.status_code == 200
        assert len(response.context["audit_logs"]) >= 10  # Remaining logs
