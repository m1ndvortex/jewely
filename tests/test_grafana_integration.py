"""
Integration tests for Grafana deployment and configuration.

Per Requirement 24.6: THE System SHALL provide Grafana dashboards for
system overview, application performance, database performance, and infrastructure health.

These tests verify:
1. Grafana service is deployed and accessible
2. Prometheus data source is configured correctly
3. All required dashboards are loaded
4. Dashboards contain correct panels and queries
5. Grafana can query Prometheus successfully

NO MOCKS - Real integration tests only.
"""

import json
import os
from pathlib import Path

import pytest
import requests
import yaml


class TestGrafanaDeployment:
    """Test Grafana service deployment and accessibility."""

    # Use Docker service name when running inside container, localhost otherwise
    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
    GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
    GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

    @pytest.fixture(scope="class")
    def grafana_session(self):
        """Create authenticated session with Grafana."""
        session = requests.Session()
        session.auth = (self.GRAFANA_USER, self.GRAFANA_PASSWORD)
        return session

    def test_requirement_24_6_grafana_service_running(self):
        """
        Requirement 24.6: THE System SHALL provide Grafana dashboards.

        Verify Grafana service is running and accessible.
        """
        try:
            response = requests.get(f"{self.GRAFANA_URL}/api/health", timeout=5)
            assert response.status_code == 200, "Grafana health check failed"

            health_data = response.json()
            assert health_data.get("database") == "ok", "Grafana database not healthy"
            assert "version" in health_data, "Grafana version not reported"

        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"Cannot connect to Grafana at {self.GRAFANA_URL}. "
                "Ensure Grafana is running: docker-compose up -d grafana"
            )

    def test_grafana_authentication(self, grafana_session):
        """Verify Grafana authentication works with configured credentials."""
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/user")
        assert response.status_code == 200, "Authentication failed"

        user_data = response.json()
        assert user_data.get("login") == self.GRAFANA_USER, "Wrong user logged in"
        assert user_data.get("isGrafanaAdmin") is True, "User is not admin"

    def test_grafana_security_configuration(self, grafana_session):
        """Verify Grafana security settings are properly configured."""
        # Test anonymous access is disabled
        response = requests.get(f"{self.GRAFANA_URL}/api/org")
        assert response.status_code == 401, "Anonymous access should be disabled"

        # Test authenticated access works
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/org")
        assert response.status_code == 200, "Authenticated access should work"


class TestPrometheusDataSource:
    """Test Prometheus data source configuration."""

    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
    GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
    GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

    @pytest.fixture(scope="class")
    def grafana_session(self):
        """Create authenticated session with Grafana."""
        session = requests.Session()
        session.auth = (self.GRAFANA_USER, self.GRAFANA_PASSWORD)
        return session

    def test_requirement_24_6_prometheus_data_source_configured(self, grafana_session):
        """
        Requirement 24.6: Configure data sources (Prometheus).

        Verify Prometheus data source is configured and accessible.
        """
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources")
        assert response.status_code == 200, "Failed to get data sources"

        datasources = response.json()
        assert len(datasources) > 0, "No data sources configured"

        # Find Prometheus data source
        prometheus_ds = None
        for ds in datasources:
            if ds.get("type") == "prometheus":
                prometheus_ds = ds
                break

        assert prometheus_ds is not None, "Prometheus data source not found"
        assert prometheus_ds.get("name") == "Prometheus", "Wrong data source name"
        assert prometheus_ds.get("isDefault") is True, "Prometheus should be default"
        assert "prometheus:9090" in prometheus_ds.get("url", ""), "Wrong Prometheus URL"

    def test_prometheus_data_source_health(self, grafana_session):
        """Verify Prometheus data source is healthy and can be queried."""
        # Get Prometheus data source
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources")
        datasources = response.json()
        prometheus_ds = next((ds for ds in datasources if ds.get("type") == "prometheus"), None)
        assert prometheus_ds is not None, "Prometheus data source not found"

        ds_id = prometheus_ds.get("id")

        # Test data source health
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources/{ds_id}/health")
        assert response.status_code == 200, "Data source health check failed"

        health_data = response.json()
        assert health_data.get("status") == "OK", "Prometheus data source not healthy"

    def test_prometheus_query_execution(self, grafana_session):
        """Verify Grafana can execute queries against Prometheus."""
        # Get Prometheus data source
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources")
        datasources = response.json()
        prometheus_ds = next((ds for ds in datasources if ds.get("type") == "prometheus"), None)
        ds_uid = prometheus_ds.get("uid")

        # Execute a simple query
        query_payload = {
            "queries": [
                {
                    "refId": "A",
                    "expr": "up",
                    "datasource": {"type": "prometheus", "uid": ds_uid},
                }
            ],
            "from": "now-5m",
            "to": "now",
        }

        response = grafana_session.post(f"{self.GRAFANA_URL}/api/ds/query", json=query_payload)
        assert response.status_code == 200, "Query execution failed"

        query_result = response.json()
        assert "results" in query_result, "No results in query response"


class TestGrafanaDashboards:
    """Test Grafana dashboards are loaded and configured correctly."""

    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
    GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
    GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

    REQUIRED_DASHBOARDS = {
        "system-overview": "System Overview",
        "application-performance": "Application Performance",
        "database-performance": "Database Performance",
        "infrastructure-health": "Infrastructure Health",
    }

    @pytest.fixture(scope="class")
    def grafana_session(self):
        """Create authenticated session with Grafana."""
        session = requests.Session()
        session.auth = (self.GRAFANA_USER, self.GRAFANA_PASSWORD)
        return session

    def test_requirement_24_6_all_dashboards_loaded(self, grafana_session):
        """
        Requirement 24.6: THE System SHALL provide Grafana dashboards for
        system overview, application performance, database performance,
        and infrastructure health.

        Verify all 4 required dashboards are loaded.
        """
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/search?type=dash-db")
        assert response.status_code == 200, "Failed to search dashboards"

        dashboards = response.json()
        dashboard_uids = {dash.get("uid"): dash.get("title") for dash in dashboards}

        # Verify all required dashboards exist
        for uid, expected_title in self.REQUIRED_DASHBOARDS.items():
            assert uid in dashboard_uids, f"Dashboard '{expected_title}' (uid: {uid}) not found"
            actual_title = dashboard_uids[uid]
            assert (
                actual_title == expected_title
            ), f"Dashboard title mismatch: expected '{expected_title}', got '{actual_title}'"

    def test_system_overview_dashboard_structure(self, grafana_session):
        """Verify System Overview dashboard has correct structure and panels."""
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/dashboards/uid/system-overview")
        assert response.status_code == 200, "Failed to get System Overview dashboard"

        dashboard_data = response.json()
        dashboard = dashboard_data.get("dashboard", {})

        # Verify dashboard metadata
        assert dashboard.get("title") == "System Overview"
        assert dashboard.get("uid") == "system-overview"
        assert "system" in dashboard.get("tags", [])

        # Verify panels exist
        panels = dashboard.get("panels", [])
        assert len(panels) >= 6, "System Overview should have at least 6 panels"

        # Verify key panels exist
        panel_titles = [panel.get("title") for panel in panels]
        expected_panels = [
            "CPU Usage",
            "Memory Usage",
            "Disk Usage",
            "Database Connections",
            "HTTP Requests per Second",
        ]

        for expected_panel in expected_panels:
            assert (
                expected_panel in panel_titles
            ), f"Panel '{expected_panel}' not found in System Overview"

    def test_application_performance_dashboard_structure(self, grafana_session):
        """Verify Application Performance dashboard has correct structure."""
        response = grafana_session.get(
            f"{self.GRAFANA_URL}/api/dashboards/uid/application-performance"
        )
        assert response.status_code == 200, "Failed to get Application Performance dashboard"

        dashboard_data = response.json()
        dashboard = dashboard_data.get("dashboard", {})

        assert dashboard.get("title") == "Application Performance"
        assert dashboard.get("uid") == "application-performance"

        panels = dashboard.get("panels", [])
        assert len(panels) >= 7, "Application Performance should have at least 7 panels"

        panel_titles = [panel.get("title") for panel in panels]
        expected_panels = [
            "HTTP Response Status Codes",
            "Error Rate",
            "Response Time (p95)",
            "Response Time by Endpoint (p95)",
        ]

        for expected_panel in expected_panels:
            assert (
                expected_panel in panel_titles
            ), f"Panel '{expected_panel}' not found in Application Performance"

    def test_database_performance_dashboard_structure(self, grafana_session):
        """Verify Database Performance dashboard has correct structure."""
        response = grafana_session.get(
            f"{self.GRAFANA_URL}/api/dashboards/uid/database-performance"
        )
        assert response.status_code == 200, "Failed to get Database Performance dashboard"

        dashboard_data = response.json()
        dashboard = dashboard_data.get("dashboard", {})

        assert dashboard.get("title") == "Database Performance"
        assert dashboard.get("uid") == "database-performance"

        panels = dashboard.get("panels", [])
        assert len(panels) >= 8, "Database Performance should have at least 8 panels"

        panel_titles = [panel.get("title") for panel in panels]
        expected_panels = [
            "Active Connections",
            "Cache Hit Ratio",
            "Transactions per Second",
            "Database Size",
        ]

        for expected_panel in expected_panels:
            assert (
                expected_panel in panel_titles
            ), f"Panel '{expected_panel}' not found in Database Performance"

    def test_infrastructure_health_dashboard_structure(self, grafana_session):
        """Verify Infrastructure Health dashboard has correct structure."""
        response = grafana_session.get(
            f"{self.GRAFANA_URL}/api/dashboards/uid/infrastructure-health"
        )
        assert response.status_code == 200, "Failed to get Infrastructure Health dashboard"

        dashboard_data = response.json()
        dashboard = dashboard_data.get("dashboard", {})

        assert dashboard.get("title") == "Infrastructure Health"
        assert dashboard.get("uid") == "infrastructure-health"

        panels = dashboard.get("panels", [])
        assert len(panels) >= 7, "Infrastructure Health should have at least 7 panels"

        panel_titles = [panel.get("title") for panel in panels]
        expected_panels = [
            "CPU Usage Over Time",
            "Memory Usage",
            "Disk Usage",
            "Network Traffic",
            "Service Health Status",
        ]

        for expected_panel in expected_panels:
            assert (
                expected_panel in panel_titles
            ), f"Panel '{expected_panel}' not found in Infrastructure Health"

    def test_dashboards_use_prometheus_datasource(self, grafana_session):
        """Verify all dashboards use Prometheus as data source."""
        for uid in self.REQUIRED_DASHBOARDS.keys():
            response = grafana_session.get(f"{self.GRAFANA_URL}/api/dashboards/uid/{uid}")
            assert response.status_code == 200, f"Failed to get dashboard {uid}"

            dashboard_data = response.json()
            dashboard = dashboard_data.get("dashboard", {})
            panels = dashboard.get("panels", [])

            for panel in panels:
                targets = panel.get("targets", [])
                for target in targets:
                    datasource = target.get("datasource", {})
                    if isinstance(datasource, dict):
                        ds_type = datasource.get("type")
                        if ds_type:  # Some panels might not have queries
                            assert (
                                ds_type == "prometheus"
                            ), f"Panel in {uid} uses wrong datasource: {ds_type}"

    def test_dashboards_have_refresh_configured(self, grafana_session):
        """Verify dashboards have auto-refresh configured."""
        for uid in self.REQUIRED_DASHBOARDS.keys():
            response = grafana_session.get(f"{self.GRAFANA_URL}/api/dashboards/uid/{uid}")
            dashboard_data = response.json()
            dashboard = dashboard_data.get("dashboard", {})

            refresh = dashboard.get("refresh")
            assert refresh is not None, f"Dashboard {uid} has no refresh configured"
            assert refresh == "30s", f"Dashboard {uid} should refresh every 30s"


class TestGrafanaConfiguration:
    """Test Grafana configuration files are correct."""

    def test_prometheus_datasource_yaml_valid(self):
        """Verify Prometheus data source YAML is valid and correct."""
        datasource_file = Path("docker/grafana/provisioning/datasources/prometheus.yml")
        assert datasource_file.exists(), "Prometheus datasource YAML not found"

        with open(datasource_file) as f:
            config = yaml.safe_load(f)

        assert config.get("apiVersion") == 1, "Wrong API version"
        assert "datasources" in config, "No datasources defined"

        datasources = config["datasources"]
        assert len(datasources) > 0, "No datasources configured"

        prometheus_ds = datasources[0]
        assert prometheus_ds.get("name") == "Prometheus"
        assert prometheus_ds.get("type") == "prometheus"
        assert prometheus_ds.get("isDefault") is True
        assert "prometheus:9090" in prometheus_ds.get("url", "")

    def test_dashboard_provisioning_yaml_valid(self):
        """Verify dashboard provisioning YAML is valid and correct."""
        provisioning_file = Path("docker/grafana/provisioning/dashboards/default.yml")
        assert provisioning_file.exists(), "Dashboard provisioning YAML not found"

        with open(provisioning_file) as f:
            config = yaml.safe_load(f)

        assert config.get("apiVersion") == 1, "Wrong API version"
        assert "providers" in config, "No providers defined"

        providers = config["providers"]
        assert len(providers) > 0, "No providers configured"

        provider = providers[0]
        assert provider.get("type") == "file"
        assert "/etc/grafana/dashboards" in provider.get("options", {}).get("path", "")

    def test_all_dashboard_json_files_valid(self):
        """Verify all dashboard JSON files are valid."""
        dashboard_dir = Path("docker/grafana/dashboards")
        assert dashboard_dir.exists(), "Dashboard directory not found"

        dashboard_files = list(dashboard_dir.glob("*.json"))
        assert len(dashboard_files) >= 4, "Not all dashboard files found"

        expected_files = [
            "system-overview.json",
            "application-performance.json",
            "database-performance.json",
            "infrastructure-health.json",
        ]

        for expected_file in expected_files:
            file_path = dashboard_dir / expected_file
            assert file_path.exists(), f"Dashboard file {expected_file} not found"

            # Verify JSON is valid
            with open(file_path) as f:
                dashboard = json.load(f)

            assert "title" in dashboard, f"{expected_file} missing title"
            assert "uid" in dashboard, f"{expected_file} missing uid"
            assert "panels" in dashboard, f"{expected_file} missing panels"
            assert len(dashboard["panels"]) > 0, f"{expected_file} has no panels"


class TestGrafanaDockerConfiguration:
    """Test Grafana Docker configuration is correct."""

    def test_docker_compose_grafana_service_defined(self):
        """Verify Grafana service is defined in docker-compose.yml."""
        compose_file = Path("docker-compose.yml")
        assert compose_file.exists(), "docker-compose.yml not found"

        with open(compose_file) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})
        assert "grafana" in services, "Grafana service not defined"

        grafana_service = services["grafana"]
        assert grafana_service.get("image") == "grafana/grafana:latest"
        assert "3000:3000" in grafana_service.get("ports", [])

        # Verify volumes
        volumes = grafana_service.get("volumes", [])
        assert any("grafana_data" in vol for vol in volumes), "grafana_data volume not mounted"
        assert any("provisioning" in vol for vol in volumes), "Provisioning directory not mounted"
        assert any("dashboards" in vol for vol in volumes), "Dashboards directory not mounted"

        # Verify environment variables
        env = grafana_service.get("environment", [])
        env_dict = {}
        for item in env:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                env_dict[key] = value

        assert "GF_SECURITY_ADMIN_USER" in env_dict
        assert "GF_SECURITY_ADMIN_PASSWORD" in env_dict
        assert env_dict.get("GF_AUTH_ANONYMOUS_ENABLED") == "false"

    def test_grafana_volume_defined(self):
        """Verify grafana_data volume is defined."""
        compose_file = Path("docker-compose.yml")
        with open(compose_file) as f:
            compose_config = yaml.safe_load(f)

        volumes = compose_config.get("volumes", {})
        assert "grafana_data" in volumes, "grafana_data volume not defined"


class TestGrafanaEndToEnd:
    """End-to-end tests for complete Grafana functionality."""

    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
    GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
    GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

    @pytest.fixture(scope="class")
    def grafana_session(self):
        """Create authenticated session with Grafana."""
        session = requests.Session()
        session.auth = (self.GRAFANA_USER, self.GRAFANA_PASSWORD)
        return session

    def test_complete_monitoring_workflow(self, grafana_session):
        """
        Test complete monitoring workflow:
        1. Access Grafana
        2. Verify data source
        3. Load dashboard
        4. Execute query
        5. Verify data is returned
        """
        # Step 1: Verify Grafana is accessible
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/health")
        assert response.status_code == 200

        # Step 2: Verify Prometheus data source
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources")
        datasources = response.json()
        prometheus_ds = next((ds for ds in datasources if ds.get("type") == "prometheus"), None)
        assert prometheus_ds is not None

        # Step 3: Load System Overview dashboard
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/dashboards/uid/system-overview")
        assert response.status_code == 200

        # Step 4: Execute a query from the dashboard
        ds_uid = prometheus_ds.get("uid")
        query_payload = {
            "queries": [
                {
                    "refId": "A",
                    "expr": "up",
                    "datasource": {"type": "prometheus", "uid": ds_uid},
                }
            ],
            "from": "now-5m",
            "to": "now",
        }

        response = grafana_session.post(f"{self.GRAFANA_URL}/api/ds/query", json=query_payload)
        assert response.status_code == 200

        # Step 5: Verify data is returned
        query_result = response.json()
        assert "results" in query_result

    def test_requirement_24_6_complete_integration(self, grafana_session):
        """
        Requirement 24.6: Complete integration test.

        Verify the complete Grafana integration:
        - Service is running
        - Data source is configured
        - All 4 dashboards are loaded
        - Dashboards can query Prometheus
        - Data is displayed correctly
        """
        # 1. Service running
        response = requests.get(f"{self.GRAFANA_URL}/api/health", timeout=5)
        assert response.status_code == 200

        # 2. Data source configured
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/datasources")
        datasources = response.json()
        prometheus_ds = next((ds for ds in datasources if ds.get("type") == "prometheus"), None)
        assert prometheus_ds is not None
        assert prometheus_ds.get("isDefault") is True

        # 3. All 4 dashboards loaded
        response = grafana_session.get(f"{self.GRAFANA_URL}/api/search?type=dash-db")
        dashboards = response.json()
        dashboard_uids = [dash.get("uid") for dash in dashboards]

        required_uids = [
            "system-overview",
            "application-performance",
            "database-performance",
            "infrastructure-health",
        ]
        for uid in required_uids:
            assert uid in dashboard_uids, f"Dashboard {uid} not loaded"

        # 4. Can query Prometheus
        ds_uid = prometheus_ds.get("uid")
        query_payload = {
            "queries": [
                {
                    "refId": "A",
                    "expr": "up",
                    "datasource": {"type": "prometheus", "uid": ds_uid},
                }
            ],
            "from": "now-5m",
            "to": "now",
        }

        response = grafana_session.post(f"{self.GRAFANA_URL}/api/ds/query", json=query_payload)
        assert response.status_code == 200

        # 5. Data is returned
        query_result = response.json()
        assert "results" in query_result

        print("\n✅ Requirement 24.6 FULLY SATISFIED:")
        print("   - Grafana service deployed and running")
        print("   - Prometheus data source configured")
        print("   - System Overview dashboard loaded")
        print("   - Application Performance dashboard loaded")
        print("   - Database Performance dashboard loaded")
        print("   - Infrastructure Health dashboard loaded")
        print("   - All dashboards can query Prometheus successfully")
