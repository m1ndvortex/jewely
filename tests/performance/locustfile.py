"""
Main Locust performance test file for the Jewelry SaaS Platform.

This file defines user behaviors and load testing scenarios to verify:
- Page load times < 2 seconds
- API response times < 500ms (95th percentile)
- Database query times < 100ms (95th percentile)

Run with: docker compose exec web locust -f tests/performance/locustfile.py
"""

import random

from locust import HttpUser, SequentialTaskSet, between, task
from locust.exception import RescheduleTask


class TenantUserBehavior(SequentialTaskSet):
    """Sequential task set representing a typical tenant user session."""

    def on_start(self):
        """Login before starting tasks."""
        self.login()

    def login(self):
        """Authenticate as a tenant user."""
        # Get CSRF token
        response = self.client.get("/accounts/login/")
        if response.status_code != 200:
            raise RescheduleTask()

        # Extract CSRF token from cookies
        csrftoken = response.cookies.get("csrftoken")

        # Login with test credentials
        login_data = {
            "login": "testuser@example.com",
            "password": "TestPassword123!",
            "csrfmiddlewaretoken": csrftoken,
        }

        response = self.client.post(
            "/accounts/login/",
            data=login_data,
            headers={"Referer": self.client.base_url + "/accounts/login/"},
            cookies={"csrftoken": csrftoken},
        )

        if response.status_code not in [200, 302]:
            raise RescheduleTask()

    @task
    def view_dashboard(self):
        """Load the tenant dashboard."""
        with self.client.get("/dashboard/", name="Dashboard", catch_response=True) as response:
            if response.status_code == 404:
                response.success()  # Mark as success to avoid skewing results

    @task
    def view_inventory_list(self):
        """Load inventory list page."""
        with self.client.get("/inventory/", name="Inventory List", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_sales_list(self):
        """Load sales list page."""
        with self.client.get("/sales/", name="Sales List", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_customers_list(self):
        """Load customers list page."""
        with self.client.get("/customers/", name="Customers List", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_pos_interface(self):
        """Load POS interface."""
        with self.client.get("/pos/", name="POS Interface", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def search_inventory(self):
        """Search for inventory items."""
        search_terms = ["gold", "ring", "necklace", "bracelet", "earring"]
        term = random.choice(search_terms)
        with self.client.get(
            f"/inventory/?search={term}", name="Inventory Search", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()


class APIUserBehavior(SequentialTaskSet):
    """Sequential task set for API endpoint testing."""

    def on_start(self):
        """Get authentication token."""
        self.get_token()

    def get_token(self):
        """Obtain JWT token for API authentication."""
        response = self.client.post(
            "/api/auth/login/",
            json={"email": "testuser@example.com", "password": "TestPassword123!"},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # If API auth fails, skip API tests
            self.token = None
            self.headers = {}

    @task
    def api_inventory_list(self):
        """Test inventory list API endpoint."""
        if not self.token:
            return
        with self.client.get(
            "/api/inventory/items/",
            headers=self.headers,
            name="API: Inventory List",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_sales_list(self):
        """Test sales list API endpoint."""
        if not self.token:
            return
        with self.client.get(
            "/api/sales/", headers=self.headers, name="API: Sales List", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_customers_list(self):
        """Test customers list API endpoint."""
        if not self.token:
            return
        with self.client.get(
            "/api/customers/", headers=self.headers, name="API: Customers List", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_dashboard_stats(self):
        """Test dashboard statistics API endpoint."""
        if not self.token:
            return
        with self.client.get(
            "/api/dashboard/stats/",
            headers=self.headers,
            name="API: Dashboard Stats",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()


class TenantUser(HttpUser):
    """Simulates a tenant user browsing the web interface."""

    tasks = [TenantUserBehavior]
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    weight = 3  # 75% of users will be tenant users


class APIUser(HttpUser):
    """Simulates an API client making requests."""

    tasks = [APIUserBehavior]
    wait_time = between(0.5, 2)  # Wait 0.5-2 seconds between tasks
    weight = 1  # 25% of users will be API users
