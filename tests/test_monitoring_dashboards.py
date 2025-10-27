"""
Tests for monitoring dashboards.

Per Requirements 7 and 24:
- Requirement 7: System Monitoring and Health Dashboard
- Requirement 24: Monitoring and Observability

Tests real monitoring functionality without mocks.
"""

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.core.models import Tenant

User = get_user_model()


class MonitoringDashboardTestCase(TestCase):
    """
    Tests for monitoring dashboard views.
    Uses real services (no mocks).
    """

    def setUp(self):
        """Set up test client and platform admin user."""
        self.client = Client()

        # Create platform admin user with unique username
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        self.admin_user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Login as platform admin
        self.client.login(username=f"admin_{unique_id}", password="testpass123")

    def test_monitoring_dashboard_accessible(self):
        """
        Requirement 7.1: Display real-time metrics for CPU usage, memory usage,
        disk space, and database connections.

        Test that monitoring dashboard is accessible to platform admins.
        """
        response = self.client.get(reverse("core:monitoring_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Monitoring")
        self.assertContains(response, "Service Status")

    def test_monitoring_dashboard_requires_admin(self):
        """Test that monitoring dashboard requires platform admin access."""
        # Create tenant for regular user
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            company_name=f"Test Shop {unique_id}", slug=f"test-shop-{unique_id}", status="ACTIVE"
        )

        # Create regular user with unique username
        User.objects.create_user(
            username=f"regular_{unique_id}",
            email=f"regular_{unique_id}@example.com",
            password="testpass123",
            role=User.TENANT_EMPLOYEE,
            tenant=tenant,
        )

        # Login as regular user
        self.client.logout()
        self.client.login(username=f"regular_{unique_id}", password="testpass123")

        response = self.client.get(reverse("core:monitoring_dashboard"))

        # Should be denied
        self.assertEqual(response.status_code, 403)

    def test_system_metrics_api(self):
        """
        Requirement 7.1: Display real-time metrics for CPU usage, memory usage,
        disk space, and database connections.

        Test system metrics API endpoint.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify CPU metrics
        self.assertIn("cpu", data)
        self.assertIn("usage_percent", data["cpu"])
        self.assertIn("count", data["cpu"])
        self.assertIn("status", data["cpu"])
        self.assertGreaterEqual(data["cpu"]["usage_percent"], 0)
        self.assertLessEqual(data["cpu"]["usage_percent"], 100)

        # Verify memory metrics
        self.assertIn("memory", data)
        self.assertIn("usage_percent", data["memory"])
        self.assertIn("total_gb", data["memory"])
        self.assertIn("used_gb", data["memory"])
        self.assertIn("available_gb", data["memory"])
        self.assertGreaterEqual(data["memory"]["usage_percent"], 0)
        self.assertLessEqual(data["memory"]["usage_percent"], 100)

        # Verify disk metrics
        self.assertIn("disk", data)
        self.assertIn("usage_percent", data["disk"])
        self.assertIn("total_gb", data["disk"])
        self.assertIn("free_gb", data["disk"])
        self.assertGreaterEqual(data["disk"]["usage_percent"], 0)
        self.assertLessEqual(data["disk"]["usage_percent"], 100)

        # Verify network metrics
        self.assertIn("network", data)
        self.assertIn("bytes_sent_mb", data["network"])
        self.assertIn("bytes_recv_mb", data["network"])

    def test_database_metrics_api(self):
        """
        Requirement 7.2: Monitor database connections, query performance.

        Test database metrics API endpoint.
        """
        # Perform some database operations to generate metrics
        Tenant.objects.count()

        response = self.client.get(reverse("core:monitoring_database_metrics"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify connection metrics
        self.assertIn("connections", data)
        if "error" not in data["connections"]:
            self.assertIn("total", data["connections"])
            self.assertIn("active", data["connections"])
            self.assertIn("idle", data["connections"])
            self.assertIn("max_connections", data["connections"])
            self.assertIn("usage_percent", data["connections"])
            self.assertGreaterEqual(data["connections"]["total"], 0)

        # Verify activity metrics
        self.assertIn("activity", data)
        if "error" not in data["activity"]:
            self.assertIn("commits", data["activity"])
            self.assertIn("rollbacks", data["activity"])
            self.assertIn("cache_hit_ratio", data["activity"])
            self.assertGreaterEqual(data["activity"]["cache_hit_ratio"], 0)
            self.assertLessEqual(data["activity"]["cache_hit_ratio"], 100)

        # Verify size metrics
        self.assertIn("size", data)
        if "error" not in data["size"]:
            self.assertIn("size_mb", data["size"])
            self.assertIn("size_gb", data["size"])
            self.assertGreater(data["size"]["size_mb"], 0)

    def test_cache_metrics_api(self):
        """
        Requirement 7.4: Monitor cache hit rates.

        Test cache metrics API endpoint.
        """
        # Perform cache operations to generate metrics
        cache.set("test_key_1", "value1", 60)
        cache.set("test_key_2", "value2", 60)
        cache.get("test_key_1")  # Hit
        cache.get("nonexistent")  # Miss

        response = self.client.get(reverse("core:monitoring_cache_metrics"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify Redis metrics
        self.assertIn("redis", data)
        if "error" not in data["redis"]:
            self.assertIn("version", data["redis"])
            self.assertIn("used_memory_mb", data["redis"])
            self.assertIn("hit_rate_percent", data["redis"])
            self.assertIn("keyspace_hits", data["redis"])
            self.assertIn("keyspace_misses", data["redis"])
            self.assertIn("total_keys", data["redis"])
            self.assertIn("connected_clients", data["redis"])
            self.assertIn("status", data["redis"])

            # Hit rate should be between 0 and 100
            self.assertGreaterEqual(data["redis"]["hit_rate_percent"], 0)
            self.assertLessEqual(data["redis"]["hit_rate_percent"], 100)

    def test_celery_metrics_api(self):
        """
        Requirement 7.2: Monitor Celery worker status and queue lengths.

        Test Celery metrics API endpoint.
        """
        response = self.client.get(reverse("core:monitoring_celery_metrics"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify worker metrics
        self.assertIn("workers", data)
        if "error" not in data["workers"]:
            self.assertIn("total_workers", data["workers"])
            self.assertIn("workers", data["workers"])
            self.assertIn("status", data["workers"])
            self.assertIsInstance(data["workers"]["workers"], list)

        # Verify queue metrics
        self.assertIn("queues", data)
        if "error" not in data["queues"]:
            self.assertIn("reserved_tasks", data["queues"])
            self.assertIn("scheduled_tasks", data["queues"])
            self.assertIn("total_pending", data["queues"])

        # Verify task metrics
        self.assertIn("tasks", data)

    def test_service_status_api(self):
        """
        Requirement 7.2: Monitor status of all critical services including Django,
        PostgreSQL, Redis, Celery, and Nginx.

        Test service status API endpoint.
        """
        response = self.client.get(reverse("core:monitoring_service_status"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Verify Django status
        self.assertIn("django", data)
        self.assertEqual(data["django"]["name"], "Django")
        self.assertEqual(data["django"]["status"], "up")

        # Verify PostgreSQL status
        self.assertIn("postgresql", data)
        self.assertEqual(data["postgresql"]["name"], "PostgreSQL")
        # Should be up since we're running tests
        self.assertEqual(data["postgresql"]["status"], "up")
        self.assertIn("version", data["postgresql"])

        # Verify Redis status
        self.assertIn("redis", data)
        self.assertEqual(data["redis"]["name"], "Redis")
        # Should be up since we're using it for cache
        self.assertEqual(data["redis"]["status"], "up")

        # Verify Celery status
        self.assertIn("celery", data)
        self.assertEqual(data["celery"]["name"], "Celery")
        # May be up or down depending on test environment
        self.assertIn(data["celery"]["status"], ["up", "down"])

    def test_metrics_api_requires_admin(self):
        """Test that metrics APIs require platform admin access."""
        # Create tenant for regular user
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            company_name=f"Test Shop {unique_id}", slug=f"test-shop-{unique_id}", status="ACTIVE"
        )

        # Create regular user with unique username
        User.objects.create_user(
            username=f"regular_{unique_id}",
            email=f"regular_{unique_id}@example.com",
            password="testpass123",
            role=User.TENANT_EMPLOYEE,
            tenant=tenant,
        )

        # Login as regular user
        self.client.logout()
        self.client.login(username=f"regular_{unique_id}", password="testpass123")

        # Try to access each API endpoint
        endpoints = [
            "core:monitoring_system_metrics",
            "core:monitoring_database_metrics",
            "core:monitoring_cache_metrics",
            "core:monitoring_celery_metrics",
            "core:monitoring_service_status",
        ]

        for endpoint in endpoints:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(
                response.status_code, 403, f"Endpoint {endpoint} should require admin access"
            )

    def test_database_connection_count(self):
        """
        Requirement 7.1: Display real-time metrics for database connections.

        Test that database connection metrics are accurate.
        """
        # Force a database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        response = self.client.get(reverse("core:monitoring_database_metrics"))
        data = json.loads(response.content)

        if "error" not in data["connections"]:
            # Should have at least one connection (ours)
            self.assertGreaterEqual(data["connections"]["total"], 1)
            self.assertGreaterEqual(data["connections"]["active"], 0)

    def test_cache_hit_rate_calculation(self):
        """
        Requirement 7.4: Monitor cache hit rates.

        Test that cache hit rate is calculated correctly.
        """
        # Perform known cache operations (don't clear cache as it might affect session)
        cache.set("hit_test_1", "value1", 60)
        cache.set("hit_test_2", "value2", 60)

        # Generate hits
        cache.get("hit_test_1")
        cache.get("hit_test_2")

        # Generate misses
        cache.get("miss_test_1")
        cache.get("miss_test_2")

        response = self.client.get(reverse("core:monitoring_cache_metrics"))

        # Check response status first
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        if "error" not in data.get("redis", {}):
            # Should have some hits and misses
            self.assertGreater(data["redis"]["keyspace_hits"], 0)
            self.assertGreater(data["redis"]["keyspace_misses"], 0)

            # Hit rate should be reasonable (between 0 and 100)
            self.assertGreaterEqual(data["redis"]["hit_rate_percent"], 0)
            self.assertLessEqual(data["redis"]["hit_rate_percent"], 100)


@pytest.mark.django_db
class MonitoringDashboardIntegrationTest:
    """Integration tests for monitoring dashboards."""

    def test_monitoring_dashboard_loads_all_metrics(self, client, admin_user):
        """Test that monitoring dashboard loads all metric types."""
        client.force_login(admin_user)

        response = client.get(reverse("core:monitoring_dashboard"))

        assert response.status_code == 200

        # Check that all tabs are present
        content = response.content.decode("utf-8")
        assert "System Overview" in content
        assert "Database" in content
        assert "Cache" in content
        assert "Celery" in content

    def test_system_metrics_status_indicators(self, client, admin_user):
        """Test that system metrics include status indicators."""
        client.force_login(admin_user)

        response = client.get(reverse("core:monitoring_system_metrics"))
        data = response.json()

        # Each metric should have a status
        assert data["cpu"]["status"] in ["ok", "warning", "critical"]
        assert data["memory"]["status"] in ["ok", "warning", "critical"]
        assert data["disk"]["status"] in ["ok", "warning", "critical"]

    def test_database_metrics_cache_hit_ratio(self, client, admin_user):
        """Test that database cache hit ratio is tracked."""
        client.force_login(admin_user)

        # Perform database operations
        from apps.core.models import Tenant

        Tenant.objects.count()

        response = client.get(reverse("core:monitoring_database_metrics"))
        data = response.json()

        if "error" not in data["activity"]:
            # Cache hit ratio should be a percentage
            assert 0 <= data["activity"]["cache_hit_ratio"] <= 100

    def test_service_status_all_services(self, client, admin_user):
        """Test that all critical services are monitored."""
        client.force_login(admin_user)

        response = client.get(reverse("core:monitoring_service_status"))
        data = response.json()

        # All critical services should be present
        assert "django" in data
        assert "postgresql" in data
        assert "redis" in data
        assert "celery" in data

        # Each service should have required fields
        for service_name, service_data in data.items():
            if service_name == "timestamp":
                continue

            assert "name" in service_data
            assert "status" in service_data
            assert "message" in service_data


@pytest.fixture
def admin_user(db):
    """Create a platform admin user for testing."""
    import uuid

    User = get_user_model()
    unique_id = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"admin_{unique_id}",
        email=f"admin_{unique_id}@example.com",
        password="testpass123",
        role=User.PLATFORM_ADMIN,
    )


class MonitoringRequirementsComplianceTest(TestCase):
    """Tests that verify compliance with specific requirements."""

    def setUp(self):
        """Set up test client and platform admin user."""
        self.client = Client()

        # Create platform admin user with unique username
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        self.admin_user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        self.client.login(username=f"admin_{unique_id}", password="testpass123")

    def test_requirement_7_1_real_time_metrics(self):
        """
        Requirement 7.1: THE System SHALL display real-time metrics for CPU usage,
        memory usage, disk space, and database connections.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))
        data = json.loads(response.content)

        # CPU usage
        self.assertIn("cpu", data)
        self.assertIn("usage_percent", data["cpu"])

        # Memory usage
        self.assertIn("memory", data)
        self.assertIn("usage_percent", data["memory"])

        # Disk space
        self.assertIn("disk", data)
        self.assertIn("usage_percent", data["disk"])

        # Database connections (from database metrics)
        db_response = self.client.get(reverse("core:monitoring_database_metrics"))
        db_data = json.loads(db_response.content)
        self.assertIn("connections", db_data)

    def test_requirement_7_2_service_monitoring(self):
        """
        Requirement 7.2: THE System SHALL monitor status of all critical services
        including Django, PostgreSQL, Redis, Celery, and Nginx.
        """
        response = self.client.get(reverse("core:monitoring_service_status"))
        data = json.loads(response.content)

        # All critical services should be monitored
        self.assertIn("django", data)
        self.assertIn("postgresql", data)
        self.assertIn("redis", data)
        self.assertIn("celery", data)

        # Each service should have status
        for service_name, service_data in data.items():
            if service_name == "timestamp":
                continue
            self.assertIn("status", service_data)
            self.assertIn(service_data["status"], ["up", "down", "degraded", "unknown"])

    def test_requirement_7_4_performance_monitoring(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times,
        database query performance, and cache hit rates.
        """
        # Database query performance
        db_response = self.client.get(reverse("core:monitoring_database_metrics"))
        db_data = json.loads(db_response.content)
        self.assertIn("activity", db_data)
        if "error" not in db_data["activity"]:
            self.assertIn("cache_hit_ratio", db_data["activity"])

        # Cache hit rates
        cache_response = self.client.get(reverse("core:monitoring_cache_metrics"))
        cache_data = json.loads(cache_response.content)
        self.assertIn("redis", cache_data)
        if "error" not in cache_data["redis"]:
            self.assertIn("hit_rate_percent", cache_data["redis"])
            self.assertIn("keyspace_hits", cache_data["redis"])
            self.assertIn("keyspace_misses", cache_data["redis"])

    def test_requirement_24_6_grafana_dashboard_foundation(self):
        """
        Requirement 24.6: THE System SHALL provide Grafana dashboards for
        system overview, application performance, database performance,
        and infrastructure health.

        This test verifies the foundation is in place (metrics collection).
        Actual Grafana integration is Task 19.4.
        """
        # Verify all metric types are available
        system_response = self.client.get(reverse("core:monitoring_system_metrics"))
        self.assertEqual(system_response.status_code, 200)

        db_response = self.client.get(reverse("core:monitoring_database_metrics"))
        self.assertEqual(db_response.status_code, 200)

        cache_response = self.client.get(reverse("core:monitoring_cache_metrics"))
        self.assertEqual(cache_response.status_code, 200)

        celery_response = self.client.get(reverse("core:monitoring_celery_metrics"))
        self.assertEqual(celery_response.status_code, 200)
