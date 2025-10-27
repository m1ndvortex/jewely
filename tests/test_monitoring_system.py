"""
Comprehensive tests for monitoring system.

This test file covers Task 19.5 requirements:
- Test metrics collection
- Test alert triggering
- Test dashboard data accuracy

Per Requirements 7 and 28:
- Requirement 7: System Monitoring and Health Dashboard
- Requirement 28: Testing requirements

Tests use real services (no mocks) per Docker-only development policy.
"""

import json
import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.core.alert_models import AlertRule, MonitoringAlert
from apps.core.alert_service import AlertService
from apps.core.models import Tenant

User = get_user_model()


class MetricsCollectionTestCase(TestCase):
    """
    Test metrics collection functionality.

    Requirement 7.1: Display real-time metrics for CPU usage, memory usage,
    disk space, and database connections.
    """

    def setUp(self):
        """Set up test client and admin user."""
        self.client = Client()
        unique_id = uuid.uuid4().hex[:8]
        self.admin_user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )
        self.client.login(username=f"admin_{unique_id}", password="testpass123")

    def test_prometheus_metrics_collection(self):
        """
        Test that Prometheus metrics endpoint collects metrics.

        Requirement 24.2: Expose Django metrics using django-prometheus.
        """
        # Logout to access metrics endpoint without authentication
        self.client.logout()

        # Get metrics (should be accessible without auth)
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Verify HTTP metrics are collected
        self.assertIn("django_http_requests_total", content)
        self.assertIn("django_http_requests_latency_seconds", content)
        self.assertIn("django_http_responses_total", content)

        # Verify metrics have actual values
        self.assertIn('method="GET"', content)

    def test_database_metrics_collection(self):
        """
        Test that database metrics are collected.

        Requirement 7.4: Monitor database query performance.
        """
        # Perform database operations
        Tenant.objects.count()
        Tenant.objects.filter(status="ACTIVE").first()

        # Logout to access metrics endpoint without authentication
        self.client.logout()

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify database metrics are collected
        self.assertIn("django_db_execute_total", content)
        self.assertIn("django_db_query_duration_seconds", content)
        self.assertIn('alias="default"', content)
        self.assertIn('vendor="postgresql"', content)

    def test_cache_metrics_collection(self):
        """
        Test that cache metrics are collected.

        Requirement 7.4: Monitor cache hit rates.
        """
        # Perform cache operations
        cache.set("test_metric_1", "value1", 60)
        cache.set("test_metric_2", "value2", 60)
        cache.get("test_metric_1")  # Hit
        cache.get("test_metric_2")  # Hit
        cache.get("nonexistent_metric")  # Miss

        # Logout to access metrics endpoint without authentication
        self.client.logout()

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify cache metrics are collected
        self.assertIn("django_cache_get_total", content)
        self.assertIn("django_cache_get_hits_total", content)
        self.assertIn("django_cache_get_misses_total", content)

    def test_system_metrics_api_collection(self):
        """
        Test that system metrics API collects real-time data.

        Requirement 7.1: Display real-time metrics.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify CPU metrics are collected
        self.assertIn("cpu", data)
        self.assertIn("usage_percent", data["cpu"])
        self.assertGreaterEqual(data["cpu"]["usage_percent"], 0)
        self.assertLessEqual(data["cpu"]["usage_percent"], 100)

        # Verify memory metrics are collected
        self.assertIn("memory", data)
        self.assertIn("usage_percent", data["memory"])
        self.assertGreaterEqual(data["memory"]["usage_percent"], 0)
        self.assertLessEqual(data["memory"]["usage_percent"], 100)

        # Verify disk metrics are collected
        self.assertIn("disk", data)
        self.assertIn("usage_percent", data["disk"])
        self.assertGreaterEqual(data["disk"]["usage_percent"], 0)
        self.assertLessEqual(data["disk"]["usage_percent"], 100)

    def test_database_connection_metrics_collection(self):
        """
        Test that database connection metrics are collected.

        Requirement 7.1: Display real-time metrics for database connections.
        """
        # Force database connections
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        response = self.client.get(reverse("core:monitoring_database_metrics"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify connection metrics are collected
        self.assertIn("connections", data)
        if "error" not in data["connections"]:
            self.assertIn("total", data["connections"])
            self.assertIn("active", data["connections"])
            self.assertIn("max_connections", data["connections"])
            self.assertGreaterEqual(data["connections"]["total"], 0)

    def test_cache_hit_rate_metrics_collection(self):
        """
        Test that cache hit rate metrics are collected accurately.

        Requirement 7.4: Monitor cache hit rates.
        """
        # Perform known cache operations
        cache.set("hit_rate_test_1", "value1", 60)
        cache.set("hit_rate_test_2", "value2", 60)

        # Generate hits
        cache.get("hit_rate_test_1")
        cache.get("hit_rate_test_2")

        # Generate misses
        cache.get("miss_test_1")
        cache.get("miss_test_2")

        response = self.client.get(reverse("core:monitoring_cache_metrics"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verify hit rate metrics are collected
        self.assertIn("redis", data)
        if "error" not in data["redis"]:
            self.assertIn("hit_rate_percent", data["redis"])
            self.assertIn("keyspace_hits", data["redis"])
            self.assertIn("keyspace_misses", data["redis"])
            self.assertGreaterEqual(data["redis"]["hit_rate_percent"], 0)
            self.assertLessEqual(data["redis"]["hit_rate_percent"], 100)


class AlertTriggeringTestCase(TestCase):
    """
    Test alert triggering functionality.

    Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
    """

    def setUp(self):
        """Set up test data."""
        AlertRule.objects.all().delete()
        MonitoringAlert.objects.all().delete()

        unique_id = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    def test_cpu_alert_triggering(self):
        """
        Test that CPU usage alerts trigger correctly.

        Requirement 7.6: Provide alert configuration for CPU.
        """
        rule = AlertRule.objects.create(
            name="High CPU Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )

        # Trigger alert with high CPU value
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_rule, rule)
        self.assertEqual(alerts[0].current_value, 85.0)
        self.assertEqual(alerts[0].status, MonitoringAlert.ACTIVE)

    def test_memory_alert_triggering(self):
        """
        Test that memory usage alerts trigger correctly.

        Requirement 7.6: Provide alert configuration for memory.
        """
        rule = AlertRule.objects.create(
            name="High Memory Alert",
            metric_type=AlertRule.MEMORY_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=85.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        # Trigger alert with high memory value
        alerts = AlertService.check_metric(AlertRule.MEMORY_USAGE, 90.0)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_rule, rule)
        self.assertEqual(alerts[0].current_value, 90.0)

    def test_disk_alert_triggering(self):
        """
        Test that disk usage alerts trigger correctly.

        Requirement 7.6: Provide alert configuration for disk space.
        """
        rule = AlertRule.objects.create(
            name="Low Disk Space Alert",
            metric_type=AlertRule.DISK_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=90.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        # Trigger alert with high disk usage
        alerts = AlertService.check_metric(AlertRule.DISK_USAGE, 95.0)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_rule, rule)
        self.assertEqual(alerts[0].current_value, 95.0)

    def test_alert_not_triggered_below_threshold(self):
        """
        Test that alerts don't trigger when below threshold.

        Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
        """
        AlertRule.objects.create(
            name="CPU Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )

        # Don't trigger alert with low CPU value
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 70.0)

        self.assertEqual(len(alerts), 0)

    def test_alert_cooldown_period(self):
        """
        Test that alert cooldown period prevents duplicate alerts.

        Requirement 7.6: Provide alert configuration.
        """
        AlertRule.objects.create(
            name="CPU Alert with Cooldown",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=75.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            cooldown_minutes=30,
            created_by=self.user,
        )

        # First alert should trigger
        alerts1 = AlertService.check_metric(AlertRule.CPU_USAGE, 80.0)
        self.assertEqual(len(alerts1), 1)

        # Second alert immediately should be blocked by cooldown
        alerts2 = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)
        self.assertEqual(len(alerts2), 0)

    def test_multiple_severity_alerts(self):
        """
        Test that multiple alert rules with different severities trigger correctly.

        Requirement 7.6: Provide alert configuration.
        """
        # Create warning rule
        rule_warning = AlertRule.objects.create(
            name="CPU Warning",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=70.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )

        # Create critical rule
        rule_critical = AlertRule.objects.create(
            name="CPU Critical",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=90.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        # Trigger with value that exceeds both thresholds
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 95.0)

        # Both alerts should trigger
        self.assertEqual(len(alerts), 2)
        alert_rules = [alert.alert_rule for alert in alerts]
        self.assertIn(rule_warning, alert_rules)
        self.assertIn(rule_critical, alert_rules)

    def test_disabled_rule_no_alert(self):
        """
        Test that disabled rules don't trigger alerts.

        Requirement 7.6: Provide alert configuration.
        """
        AlertRule.objects.create(
            name="Disabled Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=70.0,
            severity=AlertRule.WARNING,
            is_enabled=False,  # Disabled
            created_by=self.user,
        )

        # Should not trigger alert
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 80.0)

        self.assertEqual(len(alerts), 0)


class DashboardDataAccuracyTestCase(TestCase):
    """
    Test dashboard data accuracy.

    Requirement 7.1: Display real-time metrics.
    Requirement 7.2: Monitor status of all critical services.
    """

    def setUp(self):
        """Set up test client and admin user."""
        self.client = Client()
        unique_id = uuid.uuid4().hex[:8]
        self.admin_user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )
        self.client.login(username=f"admin_{unique_id}", password="testpass123")

    def test_system_metrics_accuracy(self):
        """
        Test that system metrics are accurate.

        Requirement 7.1: Display real-time metrics for CPU usage, memory usage, disk space.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))
        data = json.loads(response.content)

        # CPU metrics should be valid
        self.assertIn("cpu", data)
        self.assertGreaterEqual(data["cpu"]["usage_percent"], 0)
        self.assertLessEqual(data["cpu"]["usage_percent"], 100)
        self.assertGreater(data["cpu"]["count"], 0)

        # Memory metrics should be valid
        self.assertIn("memory", data)
        self.assertGreater(data["memory"]["total_gb"], 0)
        self.assertGreaterEqual(data["memory"]["used_gb"], 0)
        self.assertGreaterEqual(data["memory"]["available_gb"], 0)
        self.assertLessEqual(data["memory"]["usage_percent"], 100)

        # Disk metrics should be valid
        self.assertIn("disk", data)
        self.assertGreater(data["disk"]["total_gb"], 0)
        self.assertGreaterEqual(data["disk"]["used_gb"], 0)
        self.assertGreaterEqual(data["disk"]["free_gb"], 0)
        self.assertLessEqual(data["disk"]["usage_percent"], 100)

    def test_database_metrics_accuracy(self):
        """
        Test that database metrics are accurate.

        Requirement 7.2: Monitor database connections, query performance.
        """
        # Perform database operations
        Tenant.objects.count()

        response = self.client.get(reverse("core:monitoring_database_metrics"))
        data = json.loads(response.content)

        # Connection metrics should be valid
        self.assertIn("connections", data)
        if "error" not in data["connections"]:
            self.assertGreaterEqual(data["connections"]["total"], 0)
            self.assertGreaterEqual(data["connections"]["active"], 0)
            self.assertGreater(data["connections"]["max_connections"], 0)
            self.assertLessEqual(data["connections"]["usage_percent"], 100)

        # Activity metrics should be valid
        self.assertIn("activity", data)
        if "error" not in data["activity"]:
            self.assertGreaterEqual(data["activity"]["commits"], 0)
            self.assertGreaterEqual(data["activity"]["rollbacks"], 0)
            self.assertGreaterEqual(data["activity"]["cache_hit_ratio"], 0)
            self.assertLessEqual(data["activity"]["cache_hit_ratio"], 100)

    def test_cache_metrics_accuracy(self):
        """
        Test that cache metrics are accurate.

        Requirement 7.4: Monitor cache hit rates.
        """
        # Perform cache operations
        cache.set("accuracy_test_1", "value1", 60)
        cache.get("accuracy_test_1")  # Hit
        cache.get("nonexistent_accuracy")  # Miss

        response = self.client.get(reverse("core:monitoring_cache_metrics"))
        data = json.loads(response.content)

        # Redis metrics should be valid
        self.assertIn("redis", data)
        if "error" not in data["redis"]:
            self.assertIn("version", data["redis"])
            self.assertGreaterEqual(data["redis"]["used_memory_mb"], 0)
            self.assertGreaterEqual(data["redis"]["hit_rate_percent"], 0)
            self.assertLessEqual(data["redis"]["hit_rate_percent"], 100)
            self.assertGreaterEqual(data["redis"]["keyspace_hits"], 0)
            self.assertGreaterEqual(data["redis"]["keyspace_misses"], 0)

    def test_service_status_accuracy(self):
        """
        Test that service status is accurate.

        Requirement 7.2: Monitor status of all critical services.
        """
        response = self.client.get(reverse("core:monitoring_service_status"))
        data = json.loads(response.content)

        # Django should be up (we're running tests)
        self.assertIn("django", data)
        self.assertEqual(data["django"]["status"], "up")

        # PostgreSQL should be up (we're using it)
        self.assertIn("postgresql", data)
        self.assertEqual(data["postgresql"]["status"], "up")
        self.assertIn("version", data["postgresql"])

        # Redis should be up (we're using it for cache)
        self.assertIn("redis", data)
        self.assertEqual(data["redis"]["status"], "up")

        # Celery status may vary
        self.assertIn("celery", data)
        self.assertIn(data["celery"]["status"], ["up", "down"])

    def test_dashboard_loads_correctly(self):
        """
        Test that monitoring dashboard loads with correct data.

        Requirement 7.1: Display real-time metrics.
        """
        response = self.client.get(reverse("core:monitoring_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Monitoring")
        self.assertContains(response, "Service Status")

    def test_metrics_timestamp_accuracy(self):
        """
        Test that metrics include accurate timestamps.

        Requirement 7.1: Display real-time metrics.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))
        data = json.loads(response.content)

        # Should have timestamp
        self.assertIn("timestamp", data)

        # Timestamp should be recent (within last minute)
        from datetime import datetime

        from django.utils import timezone

        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        now = timezone.now()
        time_diff = (now - timestamp).total_seconds()

        self.assertLess(time_diff, 60)  # Within 1 minute

    def test_metrics_status_indicators(self):
        """
        Test that metrics include status indicators.

        Requirement 7.1: Display real-time metrics.
        """
        response = self.client.get(reverse("core:monitoring_system_metrics"))
        data = json.loads(response.content)

        # Each metric should have a status
        self.assertIn("status", data["cpu"])
        self.assertIn(data["cpu"]["status"], ["ok", "warning", "critical"])

        self.assertIn("status", data["memory"])
        self.assertIn(data["memory"]["status"], ["ok", "warning", "critical"])

        self.assertIn("status", data["disk"])
        self.assertIn(data["disk"]["status"], ["ok", "warning", "critical"])


@pytest.mark.django_db
class MonitoringIntegrationTest:
    """
    Integration tests for monitoring system.

    Tests the complete monitoring workflow.
    """

    def test_metrics_to_alert_workflow(self, client, admin_user):
        """
        Test complete workflow from metrics collection to alert triggering.

        Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
        """
        client.force_login(admin_user)

        # Create alert rule
        rule = AlertRule.objects.create(
            name="Integration Test Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=admin_user,
        )

        # Check metric (should trigger alert)
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        assert len(alerts) == 1
        assert alerts[0].alert_rule == rule

        # Verify alert appears in dashboard
        # (This would be tested in UI tests)

    def test_dashboard_reflects_current_state(self, client, admin_user):
        """
        Test that dashboard reflects current system state.

        Requirement 7.1: Display real-time metrics.
        """
        client.force_login(admin_user)

        # Get dashboard
        response = client.get(reverse("core:monitoring_dashboard"))
        assert response.status_code == 200

        # Get metrics
        metrics_response = client.get(reverse("core:monitoring_system_metrics"))
        assert metrics_response.status_code == 200

        # Metrics should be current
        data = metrics_response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data


@pytest.fixture
def admin_user(db):
    """Create a platform admin user for testing."""
    User = get_user_model()
    unique_id = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"admin_{unique_id}",
        email=f"admin_{unique_id}@example.com",
        password="testpass123",
        role=User.PLATFORM_ADMIN,
    )


class MonitoringRequirementsComplianceTest(TestCase):
    """
    Tests that verify compliance with specific requirements.
    """

    def setUp(self):
        """Set up test client and admin user."""
        self.client = Client()
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

        # Database connections
        db_response = self.client.get(reverse("core:monitoring_database_metrics"))
        db_data = json.loads(db_response.content)
        self.assertIn("connections", db_data)

    def test_requirement_7_4_performance_monitoring(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times,
        database query performance, and cache hit rates.
        """
        # Database query performance
        db_response = self.client.get(reverse("core:monitoring_database_metrics"))
        db_data = json.loads(db_response.content)
        self.assertIn("activity", db_data)

        # Cache hit rates
        cache_response = self.client.get(reverse("core:monitoring_cache_metrics"))
        cache_data = json.loads(cache_response.content)
        self.assertIn("redis", cache_data)
        if "error" not in cache_data["redis"]:
            self.assertIn("hit_rate_percent", cache_data["redis"])

    def test_requirement_7_5_alert_thresholds(self):
        """
        Requirement 7.5: THE System SHALL send alerts when system metrics
        exceed defined thresholds.
        """
        # Clean up any existing alerts for this test
        AlertRule.objects.filter(name="Test Threshold Alert").delete()
        MonitoringAlert.objects.all().delete()

        unique_id = uuid.uuid4().hex[:8]
        user = User.objects.create_user(
            username=f"test_{unique_id}",
            email=f"test_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        rule = AlertRule.objects.create(
            name="Test Threshold Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=user,
        )

        # Trigger alert
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        self.assertGreaterEqual(len(alerts), 1)
        # Find our specific alert
        our_alert = next((a for a in alerts if a.alert_rule == rule), None)
        self.assertIsNotNone(our_alert)
        self.assertEqual(our_alert.alert_rule, rule)

    def test_requirement_7_6_alert_configuration(self):
        """
        Requirement 7.6: THE System SHALL provide alert configuration for CPU,
        memory, disk space, and other metrics.
        """
        unique_id = uuid.uuid4().hex[:8]
        user = User.objects.create_user(
            username=f"test_{unique_id}",
            email=f"test_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Test CPU alert configuration
        cpu_rule = AlertRule.objects.create(
            name="CPU Alert",
            metric_type=AlertRule.CPU_USAGE,
            threshold=80.0,
            created_by=user,
        )
        self.assertEqual(cpu_rule.metric_type, AlertRule.CPU_USAGE)

        # Test memory alert configuration
        memory_rule = AlertRule.objects.create(
            name="Memory Alert",
            metric_type=AlertRule.MEMORY_USAGE,
            threshold=85.0,
            created_by=user,
        )
        self.assertEqual(memory_rule.metric_type, AlertRule.MEMORY_USAGE)

        # Test disk alert configuration
        disk_rule = AlertRule.objects.create(
            name="Disk Alert",
            metric_type=AlertRule.DISK_USAGE,
            threshold=90.0,
            created_by=user,
        )
        self.assertEqual(disk_rule.metric_type, AlertRule.DISK_USAGE)
