"""
Tests for Nginx Logging and Monitoring Configuration
Task 31.5: Configure logging and monitoring

Tests verify:
1. Access logs with response times are configured
2. Error logs are configured at appropriate levels
3. nginx-prometheus-exporter integration
4. Metrics endpoint accessibility
"""

import re
from pathlib import Path

import pytest


class TestNginxLogging:
    """Test Nginx logging configuration"""

    def test_logging_snippet_exists(self):
        """Verify logging configuration snippet exists"""
        logging_conf = Path("docker/nginx/snippets/logging.conf")
        assert logging_conf.exists(), "Logging configuration snippet not found"

        content = logging_conf.read_text()
        assert "access_log" in content, "Access log configuration missing"
        assert "error_log" in content, "Error log configuration missing"

    def test_access_log_format_includes_response_times(self):
        """Verify access log format includes response time metrics"""
        nginx_conf = Path("docker/nginx/nginx.conf")
        content = nginx_conf.read_text()

        # Check for main log format with timing variables
        assert "log_format main" in content, "Main log format not defined"
        assert "rt=$request_time" in content, "Request time not in log format"
        assert (
            "uct=" in content or "upstream_connect_time" in content
        ), "Upstream connect time not in log format"
        assert (
            "uht=" in content or "upstream_header_time" in content
        ), "Upstream header time not in log format"
        assert (
            "urt=" in content or "upstream_response_time" in content
        ), "Upstream response time not in log format"

    def test_json_log_format_configured(self):
        """Verify JSON log format is available for structured logging"""
        nginx_conf = Path("docker/nginx/nginx.conf")
        content = nginx_conf.read_text()

        assert "log_format json_combined" in content, "JSON log format not defined"
        assert "request_time" in content, "Request time not in JSON format"
        assert "upstream_response_time" in content, "Upstream response time not in JSON format"

    def test_error_log_levels_configured(self):
        """Verify error logs are configured at different levels"""
        logging_conf = Path("docker/nginx/snippets/logging.conf")
        content = logging_conf.read_text()

        # Check for standard error log
        assert re.search(
            r"error_log\s+/var/log/nginx/error\.log\s+warn", content
        ), "Standard error log not configured at warn level"

        # Check for critical error log
        assert re.search(
            r"error_log\s+/var/log/nginx/error-critical\.log\s+crit", content
        ), "Critical error log not configured"

    def test_logging_snippet_included_in_nginx_conf(self):
        """Verify logging snippet is included in main nginx.conf"""
        nginx_conf = Path("docker/nginx/nginx.conf")
        content = nginx_conf.read_text()

        assert (
            "include /etc/nginx/snippets/logging.conf" in content
        ), "Logging snippet not included in nginx.conf"

    def test_access_log_buffering_configured(self):
        """Verify access log buffering for performance"""
        logging_conf = Path("docker/nginx/snippets/logging.conf")
        content = logging_conf.read_text()

        # Check for buffer and flush settings
        assert "buffer=" in content, "Access log buffering not configured"
        assert "flush=" in content, "Access log flush interval not configured"


class TestNginxMetrics:
    """Test Nginx metrics and monitoring configuration"""

    def test_metrics_snippet_exists(self):
        """Verify metrics configuration snippet exists"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        assert metrics_conf.exists(), "Metrics configuration snippet not found"

        content = metrics_conf.read_text()
        assert "stub_status" in content, "Stub status module not configured"
        assert "/nginx_status" in content, "Metrics endpoint not configured"

    def test_stub_status_module_configured(self):
        """Verify stub_status module is enabled for metrics"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()

        # Check for stub_status configuration
        assert "location /nginx_status" in content, "Nginx status location not defined"
        assert "stub_status on" in content, "Stub status not enabled"

    def test_metrics_endpoint_access_restricted(self):
        """Verify metrics endpoint is restricted to internal networks"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()

        # Check for access restrictions
        assert "allow 127.0.0.1" in content, "Localhost access not allowed"
        assert "allow 172.16.0.0/12" in content, "Docker network access not allowed"
        assert "deny all" in content, "Public access not denied"

    def test_metrics_endpoint_no_access_logging(self):
        """Verify metrics endpoint doesn't log to access log"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()

        # Metrics scraping shouldn't clutter access logs
        assert "access_log off" in content, "Access logging not disabled for metrics"

    def test_metrics_snippet_included_in_site_config(self):
        """Verify metrics snippet is included in site configuration"""
        site_conf = Path("docker/nginx/conf.d/jewelry-shop.conf")
        content = site_conf.read_text()

        assert (
            "include /etc/nginx/snippets/metrics.conf" in content
        ), "Metrics snippet not included in site configuration"

    def test_health_check_endpoint_configured(self):
        """Verify health check endpoint is configured"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()

        assert "location /health/" in content, "Health check endpoint not configured"
        assert "proxy_pass" in content, "Health check not proxied to backend"


class TestPrometheusIntegration:
    """Test nginx-prometheus-exporter integration"""

    def test_nginx_exporter_in_docker_compose(self):
        """Verify nginx-prometheus-exporter is defined in docker-compose"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        assert "nginx_exporter:" in content, "nginx_exporter service not defined"
        assert (
            "nginx/nginx-prometheus-exporter" in content
        ), "nginx-prometheus-exporter image not specified"

    def test_nginx_exporter_scrape_uri_configured(self):
        """Verify nginx_exporter is configured to scrape nginx_status"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        # Check for scrape URI configuration
        assert (
            "--nginx.scrape-uri" in content or "nginx.scrape-uri" in content
        ), "Scrape URI not configured for nginx_exporter"
        assert "nginx_status" in content, "nginx_status endpoint not referenced"

    def test_nginx_exporter_port_exposed(self):
        """Verify nginx_exporter exposes metrics port"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        # nginx-prometheus-exporter default port is 9113
        assert "9113" in content, "nginx_exporter metrics port not exposed"

    def test_nginx_exporter_depends_on_nginx(self):
        """Verify nginx_exporter depends on nginx service"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        # Find nginx_exporter service section
        lines = content.split("\n")
        in_exporter_section = False
        found_depends_on = False

        for line in lines:
            if "nginx_exporter:" in line:
                in_exporter_section = True
            elif in_exporter_section and line.strip().startswith("depends_on:"):
                found_depends_on = True
            elif in_exporter_section and found_depends_on and "nginx" in line:
                break
            elif in_exporter_section and line.strip() and not line.startswith(" "):
                # Moved to next service
                break

        assert found_depends_on, "nginx_exporter doesn't depend on nginx service"

    def test_prometheus_scrapes_nginx_exporter(self):
        """Verify Prometheus is configured to scrape nginx_exporter"""
        prometheus_conf = Path("docker/prometheus.yml")
        content = prometheus_conf.read_text()

        assert (
            "job_name: 'nginx'" in content or 'job_name: "nginx"' in content
        ), "Nginx job not defined in Prometheus config"
        assert (
            "nginx_exporter:9113" in content
        ), "nginx_exporter target not configured in Prometheus"


class TestDockerComposeConfiguration:
    """Test Docker Compose configuration for logging and monitoring"""

    def test_nginx_logs_volume_mounted(self):
        """Verify nginx logs are persisted via volume"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        # Check for nginx logs volume
        assert "nginx_logs:" in content, "nginx_logs volume not defined"
        assert (
            "nginx_logs:/var/log/nginx" in content
        ), "nginx_logs volume not mounted in nginx service"

    def test_nginx_snippets_mounted(self):
        """Verify nginx snippets directory is mounted"""
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        assert (
            "./docker/nginx/snippets:/etc/nginx/snippets:ro" in content
        ), "Nginx snippets directory not mounted"


class TestLoggingDocumentation:
    """Test that logging configuration is documented"""

    def test_logging_snippet_has_comments(self):
        """Verify logging configuration includes explanatory comments"""
        logging_conf = Path("docker/nginx/snippets/logging.conf")
        content = logging_conf.read_text()

        # Check for documentation comments
        assert "#" in content, "No comments in logging configuration"
        assert (
            "response time" in content.lower() or "timing" in content.lower()
        ), "Response time metrics not documented"

    def test_metrics_snippet_has_comments(self):
        """Verify metrics configuration includes explanatory comments"""
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()

        # Check for documentation comments
        assert "#" in content, "No comments in metrics configuration"
        assert (
            "prometheus" in content.lower() or "metrics" in content.lower()
        ), "Prometheus integration not documented"


class TestRequirementCompliance:
    """Test compliance with Requirement 22 and 24"""

    def test_requirement_22_criterion_9_compliance(self):
        """
        Requirement 22, Criterion 9:
        THE System SHALL configure Nginx to log all requests with response times and status codes
        """
        nginx_conf = Path("docker/nginx/nginx.conf")
        content = nginx_conf.read_text()

        # Verify log format includes required fields
        assert "$status" in content, "Status code not in log format"
        assert (
            "$request_time" in content or "request_time" in content
        ), "Request time not in log format"

        # Verify access log is configured
        logging_conf = Path("docker/nginx/snippets/logging.conf")
        logging_content = logging_conf.read_text()
        assert "access_log" in logging_content, "Access log not configured"

    def test_requirement_22_criterion_10_compliance(self):
        """
        Requirement 22, Criterion 10:
        THE System SHALL configure Nginx to export metrics for Prometheus monitoring
        """
        # Verify stub_status is configured
        metrics_conf = Path("docker/nginx/snippets/metrics.conf")
        content = metrics_conf.read_text()
        assert "stub_status on" in content, "Stub status not enabled"

        # Verify nginx_exporter is configured
        docker_compose = Path("docker-compose.yml")
        compose_content = docker_compose.read_text()
        assert "nginx_exporter:" in compose_content, "nginx_exporter not configured"

    def test_requirement_24_criterion_3_compliance(self):
        """
        Requirement 24, Criterion 3:
        THE System SHALL expose Nginx metrics using nginx-prometheus-exporter
        """
        docker_compose = Path("docker-compose.yml")
        content = docker_compose.read_text()

        # Verify nginx-prometheus-exporter is deployed
        assert (
            "nginx/nginx-prometheus-exporter" in content
        ), "nginx-prometheus-exporter not deployed"

        # Verify it's configured to scrape nginx
        assert (
            "--nginx.scrape-uri" in content or "nginx.scrape-uri" in content
        ), "nginx_exporter not configured to scrape nginx"

        # Verify Prometheus scrapes it
        prometheus_conf = Path("docker/prometheus.yml")
        prom_content = prometheus_conf.read_text()
        assert (
            "nginx_exporter:9113" in prom_content
        ), "Prometheus not configured to scrape nginx_exporter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
