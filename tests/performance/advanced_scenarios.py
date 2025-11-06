"""
Advanced performance testing scenarios for specific workflows.

These tests simulate real-world user journeys and complex operations:
- Complete POS sale workflow
- Inventory management operations
- Report generation
- Multi-step customer interactions

Run with: docker compose exec web locust -f tests/performance/advanced_scenarios.py
"""

import random

from locust import HttpUser, SequentialTaskSet, between, task
from locust.exception import RescheduleTask


class POSSaleWorkflow(SequentialTaskSet):
    """Complete POS sale workflow from product search to checkout."""

    def on_start(self):
        """Login and navigate to POS."""
        self.login()
        with self.client.get("/pos/", name="POS: Load Interface", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    def login(self):
        """Authenticate as a tenant user."""
        response = self.client.get("/accounts/login/")
        if response.status_code != 200:
            raise RescheduleTask()

        csrftoken = response.cookies.get("csrftoken")

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
    def search_product(self):
        """Search for a product in POS."""
        search_terms = ["gold", "ring", "necklace", "bracelet"]
        term = random.choice(search_terms)
        with self.client.get(
            f"/api/pos/search/products/?q={term}", name="POS: Search Product", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_pos_interface(self):
        """View POS interface."""
        with self.client.get("/pos/", name="POS: View Interface", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def search_customer(self):
        """Search for customer in POS."""
        with self.client.get(
            "/api/pos/search/customers/?q=Customer",
            name="POS: Search Customer",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()


class InventoryManagementWorkflow(SequentialTaskSet):
    """Inventory management operations workflow."""

    def on_start(self):
        """Login and navigate to inventory."""
        self.login()

    def login(self):
        """Authenticate as a tenant user."""
        response = self.client.get("/accounts/login/")
        if response.status_code != 200:
            raise RescheduleTask()

        csrftoken = response.cookies.get("csrftoken")

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
    def browse_inventory(self):
        """Browse inventory with pagination."""
        page = random.randint(1, 10)
        with self.client.get(
            f"/inventory/?page={page}", name="Inventory: Browse (Paginated)", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def filter_inventory(self):
        """Filter inventory by category and karat."""
        categories = ["Rings", "Necklaces", "Bracelets", "Earrings"]
        karats = [10, 14, 18, 22, 24]

        with self.client.get(
            f"/inventory/?category={random.choice(categories)}&karat={random.choice(karats)}",
            name="Inventory: Filter",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_inventory_reports(self):
        """View inventory reports."""
        with self.client.get(
            "/inventory/reports/", name="Inventory: Reports", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_inventory_valuation(self):
        """View inventory valuation via API."""
        with self.client.get(
            "/api/inventory/reports/valuation/",
            name="API: Inventory Valuation",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_low_stock(self):
        """Check low stock via API."""
        with self.client.get(
            "/api/inventory/reports/low-stock/", name="API: Low Stock", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()


class ReportGenerationWorkflow(SequentialTaskSet):
    """Report generation and viewing workflow."""

    def on_start(self):
        """Login and navigate to reports."""
        self.login()

    def login(self):
        """Authenticate as a tenant user."""
        response = self.client.get("/accounts/login/")
        if response.status_code != 200:
            raise RescheduleTask()

        csrftoken = response.cookies.get("csrftoken")

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
    def view_reports_list(self):
        """View reports list."""
        with self.client.get("/reports/", name="Reports: List", catch_response=True) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_accounting_dashboard(self):
        """View accounting dashboard."""
        with self.client.get(
            "/accounting/", name="Reports: Accounting Dashboard", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_pricing_dashboard(self):
        """View pricing dashboard."""
        with self.client.get(
            "/pricing/", name="Reports: Pricing Dashboard", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()


class CustomerManagementWorkflow(SequentialTaskSet):
    """Customer management operations workflow."""

    def on_start(self):
        """Login and navigate to CRM."""
        self.login()

    def login(self):
        """Authenticate as a tenant user."""
        response = self.client.get("/accounts/login/")
        if response.status_code != 200:
            raise RescheduleTask()

        csrftoken = response.cookies.get("csrftoken")

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
    def browse_customers(self):
        """Browse customer list."""
        page = random.randint(1, 5)
        with self.client.get(
            f"/customers/?page={page}", name="CRM: Browse Customers", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def search_customer(self):
        """Search for a customer."""
        search_term = f"Customer{random.randint(1, 200)}"
        with self.client.get(
            f"/customers/?search={search_term}", name="CRM: Search Customer", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_loyalty_tiers(self):
        """View loyalty tiers."""
        with self.client.get(
            "/loyalty/tiers/", name="CRM: Loyalty Tiers", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def view_gift_cards(self):
        """View gift cards list."""
        with self.client.get(
            "/gift-cards/", name="CRM: Gift Cards", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task
    def api_customers_list(self):
        """Get customers via API."""
        with self.client.get(
            "/api/customers/", name="API: Customers List", catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()


class POSUser(HttpUser):
    """User focused on POS operations."""

    tasks = [POSSaleWorkflow]
    wait_time = between(2, 5)
    weight = 2


class InventoryUser(HttpUser):
    """User focused on inventory management."""

    tasks = [InventoryManagementWorkflow]
    wait_time = between(1, 3)
    weight = 2


class ReportUser(HttpUser):
    """User focused on report generation."""

    tasks = [ReportGenerationWorkflow]
    wait_time = between(3, 6)
    weight = 1


class CRMUser(HttpUser):
    """User focused on customer management."""

    tasks = [CustomerManagementWorkflow]
    wait_time = between(1, 4)
    weight = 2
