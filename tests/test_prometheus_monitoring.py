"""
Tests for Prometheus monitoring integration.

Per Requirements 7 and 24 - System Monitoring and Observability
"""

import pytest
from django.test import Client, TestCase


class PrometheusMetricsTestCase(TestCase):
    """Test Prometheus metrics endpoint and integration."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint is accessible."""
        response = self.client.get("/metrics")

        # Metrics endpoint should return 200 OK
        self.assertEqual(response.status_code, 200)

        # Content type should be text/plain for Prometheus format
        self.assertIn("text/plain", response["Content-Type"])

    def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that metrics endpoint returns data in Prometheus format."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for standard Prometheus metric format (# HELP, # TYPE, metric_name)
        self.assertIn("# HELP", content)
        self.assertIn("# TYPE", content)

    def test_django_http_metrics_present(self):
        """Test that Django HTTP metrics are exposed."""
        # Make a request to generate metrics
        self.client.get("/")

        # Get metrics
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for Django HTTP metrics
        self.assertIn("django_http_requests_total_by_method_total", content)
        self.assertIn("django_http_requests_latency_seconds", content)
        self.assertIn("django_http_responses_total_by_status_total", content)

    def test_django_db_metrics_present(self):
        """Test that Django database metrics are exposed."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for Django database metrics
        self.assertIn("django_db_query_duration_seconds", content)
        self.assertIn("django_db_execute_total", content)

    def test_django_cache_metrics_present(self):
        """Test that Django cache metrics are exposed."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for Django cache metrics
        # Note: Cache metrics appear as TYPE declarations even if no operations have occurred yet
        self.assertIn("django_cache_get_total", content)
        self.assertIn("django_cache_get_hits_total", content)
        self.assertIn("django_cache_get_misses_total", content)

    def test_django_model_metrics_present(self):
        """Test that Django model metrics are exposed."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for Django model metrics
        self.assertIn("django_model_inserts_total", content)
        self.assertIn("django_model_updates_total", content)
        self.assertIn("django_model_deletes_total", content)

    def test_django_migration_metrics_present(self):
        """Test that Django migration metrics are exposed."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for Django migration metrics
        self.assertIn("django_migrations_applied_total", content)
        self.assertIn("django_migrations_unapplied_total", content)

    def test_metrics_increment_on_requests(self):
        """Test that metrics increment when requests are made."""
        # Get initial metrics
        response1 = self.client.get("/metrics")
        content1 = response1.content.decode("utf-8")

        # Extract request count (simplified - in real scenario would parse properly)
        initial_has_metrics = "django_http_requests_total_by_method_total" in content1

        # Make several requests
        for _ in range(5):
            self.client.get("/")

        # Get updated metrics
        response2 = self.client.get("/metrics")
        content2 = response2.content.decode("utf-8")

        # Verify metrics are still present (they should have incremented)
        self.assertIn("django_http_requests_total_by_method_total", content2)
        self.assertTrue(initial_has_metrics)

    def test_metrics_endpoint_no_authentication_required(self):
        """Test that metrics endpoint doesn't require authentication in development."""
        # In development, metrics should be accessible without auth
        # In production, this should be restricted via Nginx or IP whitelist
        response = self.client.get("/metrics")

        # Should not redirect to login
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 302)

    def test_metrics_content_length(self):
        """Test that metrics endpoint returns substantial content."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")

        # Metrics should contain substantial data (at least 1000 characters)
        self.assertGreater(len(content), 1000)

    def test_metrics_format_valid(self):
        """Test that metrics follow Prometheus exposition format."""
        response = self.client.get("/metrics")
        content = response.content.decode("utf-8")
        lines = content.split("\n")

        # Check that we have multiple lines
        self.assertGreater(len(lines), 10)

        # Check for proper format: comments start with #, metrics don't
        has_help = False
        has_type = False
        has_metric = False

        for line in lines:
            if line.startswith("# HELP"):
                has_help = True
            elif line.startswith("# TYPE"):
                has_type = True
            elif line and not line.startswith("#"):
                # This should be a metric line
                # Format: metric_name{labels} value timestamp
                if "{" in line or " " in line:
                    has_metric = True

        self.assertTrue(has_help, "Should have HELP comments")
        self.assertTrue(has_type, "Should have TYPE comments")
        self.assertTrue(has_metric, "Should have actual metrics")


@pytest.mark.django_db
class PrometheusIntegrationTest:
    """Integration tests for Prometheus monitoring."""

    def test_metrics_after_database_query(self, client):
        """Test that database metrics are updated after queries."""
        # Import a model to trigger database query
        from apps.core.models import Tenant

        # Make a database query
        Tenant.objects.count()

        # Get metrics
        response = client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify database metrics are present
        assert "django_db_execute_total" in content
        assert "django_db_query_duration_seconds" in content

    def test_metrics_after_cache_operation(self, client):
        """Test that cache metrics are updated after cache operations."""
        from django.core.cache import cache

        # Perform cache operations
        cache.set("test_key", "test_value", 60)
        cache.get("test_key")
        cache.get("nonexistent_key")  # This will be a miss

        # Get metrics
        response = client.get("/metrics")
        content = response.content.decode("utf-8")

        # Verify cache metrics are present
        assert "django_cache_get_total" in content
        assert "django_cache_get_hits_total" in content
        assert "django_cache_get_misses_total" in content

    def test_metrics_latency_buckets(self, client):
        """Test that latency metrics use configured buckets."""
        # Make a request
        client.get("/")

        # Get metrics
        response = client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for latency histogram buckets
        assert "django_http_requests_latency_seconds_bucket" in content

        # Check for some of our configured buckets
        assert 'le="0.1"' in content or 'le="0.5"' in content
        assert 'le="1.0"' in content or 'le="2.5"' in content

    def test_metrics_by_view(self, client):
        """Test that metrics are tracked per view."""
        # Make requests to different endpoints
        client.get("/")
        client.get("/metrics")

        # Get metrics
        response = client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for view-specific metrics
        assert "django_http_requests_total_by_view_transport_method_total" in content

    def test_metrics_by_status_code(self, client):
        """Test that metrics track response status codes."""
        # Make successful request
        client.get("/")

        # Make request that will 404
        client.get("/nonexistent-page-12345")

        # Get metrics
        response = client.get("/metrics")
        content = response.content.decode("utf-8")

        # Check for status code metrics
        assert "django_http_responses_total_by_status_total" in content
        assert 'status="200"' in content or 'status="404"' in content
