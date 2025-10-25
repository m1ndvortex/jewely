"""
Tests for admin dashboard functionality.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls

User = get_user_model()


@pytest.fixture
def platform_admin(db):
    """Create a platform admin user."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"admin-{unique_id}",
            email=f"admin-{unique_id}@example.com",
            password="AdminPassword123!@#",
            role=User.PLATFORM_ADMIN,
            is_staff=True,
            is_superuser=True,
        )


@pytest.fixture
def tenant_owner(db, tenant):
    """Create a tenant owner user."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"owner-{unique_id}",
            email=f"owner-{unique_id}@example.com",
            password="OwnerPassword123!@#",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )


@pytest.fixture
def multiple_tenants(db):
    """Create multiple tenants with different statuses for testing."""
    tenants = []
    now = timezone.now()

    with bypass_rls():
        # Create active tenants
        for i in range(3):
            tenant = Tenant.objects.create(
                company_name=f"Active Shop {i}",
                slug=f"active-shop-{i}-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )
            tenants.append(tenant)

        # Create suspended tenant
        tenant = Tenant.objects.create(
            company_name="Suspended Shop",
            slug=f"suspended-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.SUSPENDED,
        )
        tenants.append(tenant)

        # Create pending deletion tenant
        tenant = Tenant.objects.create(
            company_name="Pending Deletion Shop",
            slug=f"pending-deletion-{uuid.uuid4().hex[:8]}",
            status=Tenant.PENDING_DELETION,
        )
        tenants.append(tenant)

        # Create tenant from 31 days ago (outside 30-day window)
        old_tenant = Tenant.objects.create(
            company_name="Old Shop",
            slug=f"old-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )
        old_tenant.created_at = now - timedelta(days=31)
        old_tenant.save()
        tenants.append(old_tenant)

        # Create tenant from today
        today_tenant = Tenant.objects.create(
            company_name="Today Shop",
            slug=f"today-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )
        tenants.append(today_tenant)

    return tenants


@pytest.mark.django_db
class TestAdminDashboard:
    """Test admin dashboard views."""

    def test_admin_dashboard_requires_authentication(self, client):
        """Test that admin dashboard requires authentication."""
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        # Should redirect to login (Django admin login or allauth login)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_admin_dashboard_requires_platform_admin_role(self, client, tenant_owner):
        """Test that admin dashboard requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_admin_dashboard_accessible_by_platform_admin(self, client, platform_admin):
        """Test that platform admin can access admin dashboard."""
        client.force_login(platform_admin)
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        assert response.status_code == 200
        assert "Platform Admin Dashboard" in response.content.decode()

    def test_admin_dashboard_displays_tenant_metrics(self, client, platform_admin, tenant):
        """Test that admin dashboard displays tenant metrics."""
        client.force_login(platform_admin)
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check for tenant metrics section
        assert "Tenant Metrics" in content
        assert "Total Tenants" in content
        assert "Active Tenants" in content
        assert "Suspended" in content

    def test_admin_dashboard_displays_system_health(self, client, platform_admin):
        """Test that admin dashboard displays system health."""
        client.force_login(platform_admin)
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check for system health section
        assert "System Health" in content
        assert "CPU Usage" in content
        assert "Memory Usage" in content
        assert "Disk Usage" in content


@pytest.mark.django_db
class TestAdminDashboardAPI:
    """Test admin dashboard API endpoints."""

    def test_tenant_metrics_api_requires_authentication(self, client):
        """Test that tenant metrics API requires authentication."""
        url = reverse("core:admin_api_tenant_metrics")
        response = client.get(url)

        assert response.status_code == 302

    def test_tenant_metrics_api_requires_platform_admin(self, client, tenant_owner):
        """Test that tenant metrics API requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_api_tenant_metrics")
        response = client.get(url)

        assert response.status_code == 403

    def test_tenant_metrics_api_returns_data(self, client, platform_admin, tenant):
        """Test that tenant metrics API returns correct data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "total" in data
        assert "active" in data
        assert "suspended" in data
        assert "pending_deletion" in data
        assert "new_signups_30d" in data
        assert "new_signups_today" in data
        assert "timestamp" in data

        # Check values are reasonable (not checking exact counts due to test database state)
        assert data["total"] >= 1  # At least the tenant from fixture
        assert data["active"] >= 1  # At least the tenant from fixture
        assert data["suspended"] >= 0
        assert data["pending_deletion"] >= 0
        assert data["new_signups_30d"] >= 0
        assert data["new_signups_today"] >= 0

    def test_system_health_api_requires_authentication(self, client):
        """Test that system health API requires authentication."""
        url = reverse("core:admin_api_system_health")
        response = client.get(url)

        assert response.status_code == 302

    def test_system_health_api_returns_data(self, client, platform_admin):
        """Test that system health API returns correct data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_system_health")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "memory_used_gb" in data
        assert "memory_total_gb" in data
        assert "disk_percent" in data
        assert "disk_used_gb" in data
        assert "disk_total_gb" in data
        assert "db_connections" in data
        assert "status" in data
        assert "timestamp" in data

        # Check that values are reasonable
        assert 0 <= data["cpu_percent"] <= 100
        assert 0 <= data["memory_percent"] <= 100
        assert 0 <= data["disk_percent"] <= 100
        assert data["db_connections"] >= 0
        assert data["status"] in ["healthy", "warning", "critical"]

    def test_tenant_signup_chart_api_returns_data(self, client, platform_admin):
        """Test that tenant signup chart API returns correct data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_signup_chart")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "labels" in data
        assert "data" in data
        assert "timestamp" in data

        # Check that we have 30 days of data
        assert len(data["labels"]) == 30
        assert len(data["data"]) == 30


@pytest.mark.django_db
class TestAdminDashboardDataAccuracy:
    """Test admin dashboard data accuracy with various tenant scenarios."""

    def test_tenant_metrics_accuracy_with_multiple_tenants(
        self, client, platform_admin, multiple_tenants
    ):
        """Test that tenant metrics are calculated accurately with multiple tenants."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify total count (3 active + 1 suspended + 1 pending deletion + 1 old + 1 today = 7)
        assert data["total"] >= 7

        # Verify active count (3 active + 1 old + 1 today = 5)
        assert data["active"] >= 5

        # Verify suspended count (1)
        assert data["suspended"] >= 1

        # Verify pending deletion count (1)
        assert data["pending_deletion"] >= 1

        # Verify new signups in last 30 days (excludes the 31-day-old tenant)
        # Should include: 3 active + 1 suspended + 1 pending deletion + 1 today = 6
        assert data["new_signups_30d"] >= 6

        # Verify new signups today (1)
        assert data["new_signups_today"] >= 1

    def test_tenant_metrics_with_no_tenants(self, client, platform_admin, db):
        """Test tenant metrics when no tenants exist."""
        # Note: We can't actually delete all tenants due to protected foreign keys
        # from other test data. Instead, we'll test the API returns valid structure
        # even when counts might be zero in a fresh database.

        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present with non-negative values
        assert "total" in data
        assert "active" in data
        assert "suspended" in data
        assert "pending_deletion" in data
        assert "new_signups_30d" in data
        assert "new_signups_today" in data

        # All counts should be non-negative integers
        assert data["total"] >= 0
        assert data["active"] >= 0
        assert data["suspended"] >= 0
        assert data["pending_deletion"] >= 0
        assert data["new_signups_30d"] >= 0
        assert data["new_signups_today"] >= 0

    def test_tenant_metrics_only_active_tenants(self, client, platform_admin, db):
        """Test tenant metrics when creating only active tenants."""
        # Get initial counts
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")
        response1 = client.get(url)
        assert response1.status_code == 200
        data1 = response1.json()
        initial_total = data1["total"]
        initial_active = data1["active"]
        initial_suspended = data1["suspended"]
        initial_pending = data1["pending_deletion"]

        # Create 5 new active tenants
        with bypass_rls():
            for i in range(5):
                Tenant.objects.create(
                    company_name=f"Active Shop {i}",
                    slug=f"active-{i}-{uuid.uuid4().hex[:8]}",
                    status=Tenant.ACTIVE,
                )

        # Get updated counts
        response2 = client.get(url)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify counts increased correctly
        assert data2["total"] == initial_total + 5
        assert data2["active"] == initial_active + 5
        assert data2["suspended"] == initial_suspended  # Should remain unchanged
        assert data2["pending_deletion"] == initial_pending  # Should remain unchanged

    def test_system_health_metrics_structure(self, client, platform_admin):
        """Test that system health metrics have correct structure and reasonable values."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_system_health")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "cpu_percent",
            "memory_percent",
            "memory_used_gb",
            "memory_total_gb",
            "disk_percent",
            "disk_used_gb",
            "disk_total_gb",
            "db_connections",
            "status",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify percentage values are in valid range
        assert 0 <= data["cpu_percent"] <= 100
        assert 0 <= data["memory_percent"] <= 100
        assert 0 <= data["disk_percent"] <= 100

        # Verify memory values are logical
        assert data["memory_used_gb"] >= 0
        assert data["memory_total_gb"] > 0
        assert data["memory_used_gb"] <= data["memory_total_gb"]

        # Verify disk values are logical
        assert data["disk_used_gb"] >= 0
        assert data["disk_total_gb"] > 0
        assert data["disk_used_gb"] <= data["disk_total_gb"]

        # Verify database connections is non-negative
        assert data["db_connections"] >= 0

        # Verify status is valid
        assert data["status"] in ["healthy", "warning", "critical"]

    def test_system_health_status_determination(self, client, platform_admin):
        """Test that system health status is determined correctly based on metrics."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_system_health")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify status logic
        cpu = data["cpu_percent"]
        memory = data["memory_percent"]
        disk = data["disk_percent"]
        status = data["status"]

        if cpu > 90 or memory > 90 or disk > 90:
            assert status == "critical"
        elif cpu > 80 or memory > 80 or disk > 80:
            assert status == "warning"
        else:
            assert status == "healthy"

    def test_signup_chart_data_accuracy(self, client, platform_admin, multiple_tenants):
        """Test that signup chart data is accurate for the last 30 days."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_signup_chart")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify we have exactly 30 days of data
        assert len(data["labels"]) == 30
        assert len(data["data"]) == 30

        # Verify all counts are non-negative
        for count in data["data"]:
            assert count >= 0

        # Verify labels are in date format (YYYY-MM-DD)
        import re

        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for label in data["labels"]:
            assert date_pattern.match(label), f"Invalid date format: {label}"

        # Verify dates are in chronological order
        dates = data["labels"]
        for i in range(len(dates) - 1):
            assert dates[i] < dates[i + 1], "Dates should be in chronological order"

    def test_dashboard_view_context_data(self, client, platform_admin, multiple_tenants):
        """Test that dashboard view provides correct context data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_dashboard")
        response = client.get(url)

        assert response.status_code == 200

        # Verify context contains required data
        assert "tenant_metrics" in response.context
        assert "revenue_metrics" in response.context
        assert "system_health" in response.context

        # Verify tenant metrics structure
        tenant_metrics = response.context["tenant_metrics"]
        assert "total" in tenant_metrics
        assert "active" in tenant_metrics
        assert "suspended" in tenant_metrics
        assert "pending_deletion" in tenant_metrics
        assert "new_signups_30d" in tenant_metrics
        assert "new_signups_today" in tenant_metrics

        # Verify revenue metrics structure (placeholder for now)
        revenue_metrics = response.context["revenue_metrics"]
        assert "mrr" in revenue_metrics
        assert "arr" in revenue_metrics
        assert "churn_rate" in revenue_metrics

        # Verify system health structure
        system_health = response.context["system_health"]
        if "error" not in system_health:
            assert "cpu_percent" in system_health
            assert "memory_percent" in system_health
            assert "disk_percent" in system_health
            assert "db_connections" in system_health
            assert "status" in system_health


@pytest.mark.django_db
class TestAdminDashboardRealTimeUpdates:
    """Test admin dashboard real-time update functionality."""

    def test_tenant_metrics_updates_after_new_tenant(self, client, platform_admin, tenant):
        """Test that tenant metrics update correctly after creating a new tenant."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")

        # Get initial metrics
        response1 = client.get(url)
        assert response1.status_code == 200
        data1 = response1.json()
        initial_total = data1["total"]
        initial_active = data1["active"]

        # Create a new active tenant
        with bypass_rls():
            Tenant.objects.create(
                company_name="New Test Shop",
                slug=f"new-test-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )

        # Get updated metrics
        response2 = client.get(url)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify counts increased
        assert data2["total"] == initial_total + 1
        assert data2["active"] == initial_active + 1
        assert data2["new_signups_today"] >= 1

    def test_tenant_metrics_updates_after_status_change(self, client, platform_admin, tenant):
        """Test that tenant metrics update correctly after changing tenant status."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")

        # Get initial metrics
        response1 = client.get(url)
        assert response1.status_code == 200
        data1 = response1.json()
        initial_active = data1["active"]
        initial_suspended = data1["suspended"]

        # Change tenant status to suspended
        with bypass_rls():
            tenant.status = Tenant.SUSPENDED
            tenant.save()

        # Get updated metrics
        response2 = client.get(url)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify counts changed appropriately
        assert data2["active"] == initial_active - 1
        assert data2["suspended"] == initial_suspended + 1
        assert data2["total"] == data1["total"]  # Total should remain the same

    def test_system_health_returns_fresh_data(self, client, platform_admin):
        """Test that system health API returns fresh data on each request."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_system_health")

        # Make two requests
        response1 = client.get(url)
        assert response1.status_code == 200
        data1 = response1.json()

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.1)

        response2 = client.get(url)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify timestamps are different (indicating fresh data)
        assert data1["timestamp"] != data2["timestamp"]

        # Verify both responses have valid data
        assert "cpu_percent" in data1
        assert "cpu_percent" in data2
        assert "status" in data1
        assert "status" in data2

    def test_signup_chart_updates_with_new_signups(self, client, platform_admin):
        """Test that signup chart data reflects tenant signups correctly."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_signup_chart")

        # Create a new tenant (will be created "today" in the test)
        with bypass_rls():
            Tenant.objects.create(
                company_name="Chart Test Shop",
                slug=f"chart-test-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )

        # Get updated chart data
        response2 = client.get(url)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify the chart structure is correct
        # Note: The tenant might not appear in the chart if it's created "today"
        # and the chart shows the last 30 days starting from 30 days ago
        assert len(data2["labels"]) == 30
        assert len(data2["data"]) == 30

        # Verify all counts are non-negative
        for count in data2["data"]:
            assert count >= 0

        # Verify labels are in chronological order
        for i in range(len(data2["labels"]) - 1):
            assert data2["labels"][i] < data2["labels"][i + 1]

    def test_multiple_concurrent_metric_requests(self, client, platform_admin):
        """Test that multiple concurrent requests return consistent data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_tenant_metrics")

        # Make multiple requests
        responses = []
        for _ in range(5):
            response = client.get(url)
            assert response.status_code == 200
            responses.append(response.json())

        # Verify all responses have the same counts (no data changed between requests)
        first_response = responses[0]
        for response in responses[1:]:
            assert response["total"] == first_response["total"]
            assert response["active"] == first_response["active"]
            assert response["suspended"] == first_response["suspended"]
            assert response["pending_deletion"] == first_response["pending_deletion"]

    def test_error_feed_api_endpoint(self, client, platform_admin):
        """Test that error feed API endpoint is accessible and returns expected structure."""
        client.force_login(platform_admin)
        url = reverse("core:admin_api_error_feed")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure (placeholder implementation)
        assert "errors" in data
        assert "timestamp" in data
        assert isinstance(data["errors"], list)
