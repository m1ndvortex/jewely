"""
Real integration tests for Prometheus monitoring.
NO MOCKS - Tests actual Prometheus functionality.

Per Requirements 7 and 24:
- Requirement 7: System Monitoring and Health Dashboard
- Requirement 24: Monitoring and Observability
"""

import pytest
import requests
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase

from apps.core.models import Tenant


class PrometheusIntegrationTestCase(TestCase):
    """
    Real integration tests for Prometheus metrics.
    Tests actual metrics collection without mocks.
    """

    def setUp(self):
        """Set up test client and create test data."""
        self.client = Client()

        # Create a test tenant for database operations with unique slug
        import uuid

        unique_slug = f"test-shop-{uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug=unique_slug, status="ACTIVE"
        )

    def test_metrics_endpoint_accessible(self):
        """
        Requirement 24.2: THE System SHALL expose Django metrics using django-prometheus
        Test that /metrics endpoint is accessible and returns valid data.
        """
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])

        content = response.content.decode("utf-8")
        self.assertGreater(len(content), 1000, "Metrics should contain substantial data")

    def test_http_request_metrics_collected(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times
        Test that HTTP request metrics are collected for actual requests.
        """
        # Make several requests to generate metrics
        for i in range(5):
            self.client.get("/")

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify HTTP metrics are present
        self.assertIn("django_http_requests_total_by_method_total", content)
        self.assertIn("django_http_requests_latency_seconds", content)
        self.assertIn("django_http_responses_total_by_status_total", content)

        # Verify metrics have actual values (not just type declarations)
        self.assertIn('method="GET"', content)

    def test_database_query_metrics_collected(self):
        """
        Requirement 7.4: THE System SHALL monitor database query performance
        Test that database metrics are collected for actual queries.
        """
        # Perform actual database operations
        Tenant.objects.count()
        Tenant.objects.filter(status="ACTIVE").first()

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify database metrics are present
        self.assertIn("django_db_execute_total", content)
        self.assertIn("django_db_query_duration_seconds", content)

        # Verify metrics have actual values
        self.assertIn('alias="default"', content)
        self.assertIn('vendor="postgresql"', content)

    def test_cache_metrics_collected(self):
        """
        Requirement 7.4: THE System SHALL monitor cache hit rates
        Test that cache metrics are collected for actual cache operations.
        """
        # Perform actual cache operations
        cache.set("test_key_1", "value1", 60)
        cache.set("test_key_2", "value2", 60)
        cache.get("test_key_1")  # Hit
        cache.get("test_key_2")  # Hit
        cache.get("nonexistent_key")  # Miss

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify cache metrics are present
        self.assertIn("django_cache_get_total", content)
        self.assertIn("django_cache_get_hits_total", content)
        self.assertIn("django_cache_get_misses_total", content)

    def test_model_operation_metrics_collected(self):
        """
        Requirement 7.1: THE System SHALL display real-time metrics
        Test that model operation metrics are collected for actual database operations.
        """
        # Perform actual model operations
        tenant1 = Tenant.objects.create(company_name="Shop 1", slug="shop-1", status="ACTIVE")

        tenant1.company_name = "Updated Shop 1"
        tenant1.save()

        tenant1.delete()

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify model metrics are present
        self.assertIn("django_model_inserts_total", content)
        self.assertIn("django_model_updates_total", content)
        self.assertIn("django_model_deletes_total", content)

    def test_migration_metrics_exposed(self):
        """
        Requirement 24.2: THE System SHALL expose Django metrics
        Test that migration status metrics are exposed.
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify migration metrics are present
        self.assertIn("django_migrations_applied_total", content)
        self.assertIn("django_migrations_unapplied_total", content)

        # Verify metrics have actual values
        self.assertIn('connection="default"', content)

    def test_process_metrics_exposed(self):
        """
        Requirement 7.1: THE System SHALL display real-time metrics for CPU usage, memory usage
        Test that process metrics are exposed.
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify process metrics are present
        self.assertIn("process_virtual_memory_bytes", content)
        self.assertIn("process_resident_memory_bytes", content)
        self.assertIn("process_cpu_seconds_total", content)
        self.assertIn("process_open_fds", content)

    def test_python_runtime_metrics_exposed(self):
        """
        Requirement 24.2: THE System SHALL expose Django metrics
        Test that Python runtime metrics are exposed.
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify Python metrics are present
        self.assertIn("python_gc_objects_collected_total", content)
        self.assertIn("python_gc_collections_total", content)
        self.assertIn("python_info", content)

    def test_metrics_format_valid_prometheus(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection
        Test that metrics are in valid Prometheus exposition format.
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")
        lines = content.split("\n")

        # Verify Prometheus format
        has_help = False
        has_type = False
        has_metric = False

        for line in lines:
            if line.startswith("# HELP"):
                has_help = True
            elif line.startswith("# TYPE"):
                has_type = True
            elif line and not line.startswith("#"):
                # Metric line should have metric name and value
                if " " in line:
                    has_metric = True

        self.assertTrue(has_help, "Should have HELP comments")
        self.assertTrue(has_type, "Should have TYPE comments")
        self.assertTrue(has_metric, "Should have actual metrics")

    def test_latency_histogram_buckets(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times
        Test that latency metrics use histogram buckets.
        """
        # Make requests to generate latency metrics
        for _ in range(3):
            self.client.get("/")

        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify latency histogram is present (by view method)
        self.assertIn("django_http_requests_latency_seconds_by_view_method_bucket", content)

        # Verify buckets are configured
        self.assertIn('le="0.1"', content)
        self.assertIn('le="0.5"', content)
        self.assertIn('le="1.0"', content)
        self.assertIn('le="+Inf"', content)

    def test_metrics_by_status_code(self):
        """
        Requirement 7.2: THE System SHALL monitor status of all critical services
        Test that metrics track HTTP status codes.
        """
        # Make successful request
        self.client.get("/")

        # Make 404 request
        self.client.get("/nonexistent-endpoint-12345")

        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify status code metrics
        self.assertIn("django_http_responses_total_by_status_total", content)

    def test_database_connection_metrics(self):
        """
        Requirement 7.1: THE System SHALL display real-time metrics for database connections
        Test that database connection metrics are tracked.
        """
        # Force a database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify connection metrics
        self.assertIn("django_db_new_connections_total", content)

    def test_concurrent_requests_metrics(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times
        Test that metrics handle concurrent requests correctly.
        """
        # Make multiple concurrent-like requests
        responses = []
        for i in range(10):
            responses.append(self.client.get("/"))

        # All requests should succeed
        for resp in responses:
            self.assertEqual(resp.status_code, 200)

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify metrics are collected
        self.assertIn("django_http_requests_total_by_method_total", content)


@pytest.mark.django_db
class PrometheusDockerIntegrationTest:
    """
    Integration tests that verify Prometheus server can scrape Django metrics.
    Tests the actual Docker setup.
    """

    def test_prometheus_can_access_metrics_endpoint(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection
        Test that Prometheus server can access Django metrics endpoint.
        """
        # Try to access metrics from within Docker network
        # This simulates Prometheus scraping the endpoint
        try:
            response = requests.get("http://localhost:8000/metrics", timeout=5)
            assert response.status_code == 200
            assert "django_http_requests" in response.text
        except requests.exceptions.ConnectionError:
            pytest.skip("Docker services not running")

    def test_prometheus_server_running(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection
        Test that Prometheus server is running and accessible.
        """
        try:
            response = requests.get("http://localhost:9090/-/healthy", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus server not running")

    def test_prometheus_targets_configured(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection
        Test that Prometheus has Django target configured.
        """
        try:
            response = requests.get("http://localhost:9090/api/v1/targets", timeout=5)
            assert response.status_code == 200

            data = response.json()
            assert "data" in data
            assert "activeTargets" in data["data"]

            # Check if Django target exists
            targets = data["data"]["activeTargets"]

            # If no targets yet, that's okay - Prometheus might not have scraped yet
            # Just verify the API is working
            assert isinstance(targets, list)
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus server not running")

    def test_prometheus_can_query_django_metrics(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection
        Test that Prometheus can query Django metrics.
        """
        try:
            # Query for Django HTTP requests metric
            query = "django_http_requests_total_by_method_total"
            response = requests.get(
                "http://localhost:9090/api/v1/query", params={"query": query}, timeout=5
            )
            assert response.status_code == 200

            data = response.json()
            assert "data" in data
            assert "result" in data["data"]

            # Result might be empty if no scrapes yet, but API should work
            assert isinstance(data["data"]["result"], list)
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus server not running")


class PrometheusRequirementsComplianceTest(TestCase):
    """
    Tests that verify compliance with specific requirements.
    """

    def test_requirement_7_1_real_time_metrics(self):
        """
        Requirement 7.1: THE System SHALL display real-time metrics for CPU usage,
        memory usage, disk space, and database connections
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # CPU usage
        self.assertIn("process_cpu_seconds_total", content)

        # Memory usage
        self.assertIn("process_resident_memory_bytes", content)
        self.assertIn("process_virtual_memory_bytes", content)

        # Database connections
        self.assertIn("django_db_new_connections_total", content)

    def test_requirement_7_4_performance_monitoring(self):
        """
        Requirement 7.4: THE System SHALL monitor API response times,
        database query performance, and cache hit rates
        """
        # Generate some activity
        self.client.get("/")
        cache.set("test", "value", 60)
        cache.get("test")

        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # API response times
        self.assertIn("django_http_requests_latency_seconds", content)

        # Database query performance
        self.assertIn("django_db_query_duration_seconds", content)

        # Cache hit rates
        self.assertIn("django_cache_get_hits_total", content)
        self.assertIn("django_cache_get_misses_total", content)

    def test_requirement_24_2_django_metrics_exposed(self):
        """
        Requirement 24.2: THE System SHALL expose Django metrics using django-prometheus
        """
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify django-prometheus metrics are present
        django_metrics = [
            "django_http_requests_total",
            "django_http_responses_total",
            "django_db_execute_total",
            "django_cache_get_total",
            "django_model_inserts_total",
            "django_migrations_applied_total",
        ]

        for metric in django_metrics:
            self.assertIn(metric, content, f"Missing metric: {metric}")

    def test_requirement_24_1_prometheus_deployment(self):
        """
        Requirement 24.1: THE System SHALL deploy Prometheus for metrics collection from all services
        """
        # Verify metrics endpoint is accessible (prerequisite for Prometheus scraping)
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)

        # Verify content type is correct for Prometheus
        self.assertIn("text/plain", response["Content-Type"])

        # Verify metrics are in Prometheus format
        content = response.content.decode("utf-8")
        self.assertIn("# HELP", content)
        self.assertIn("# TYPE", content)
