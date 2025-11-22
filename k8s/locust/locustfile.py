"""
Locust Load Testing for Jewelry Shop SaaS Platform
===================================================
This file defines comprehensive load test scenarios for the jewelry shop platform.
Tests simulate realistic user behavior with 1000 concurrent users over 30 minutes.
"""

from locust import HttpUser, task, between, events
import random
import json
import time
from datetime import datetime

# Test data
SAMPLE_PRODUCTS = [
    {"name": "Gold Ring 18K", "sku": "GR-001", "price": 299.99},
    {"name": "Diamond Necklace", "sku": "DN-002", "price": 1499.99},
    {"name": "Silver Bracelet", "sku": "SB-003", "price": 89.99},
    {"name": "Pearl Earrings", "sku": "PE-004", "price": 199.99},
    {"name": "Gold Chain 22K", "sku": "GC-005", "price": 599.99},
]

SAMPLE_CUSTOMERS = [
    {"name": "Ahmad Hassan", "phone": "+989121234567"},
    {"name": "Sara Ahmadi", "phone": "+989129876543"},
    {"name": "Ali Rezaei", "phone": "+989131112222"},
    {"name": "Maryam Karimi", "phone": "+989143334444"},
]


class JewelryShopUser(HttpUser):
    """
    Simulates a jewelry shop employee using the system.
    Performs realistic tasks like viewing dashboard, managing inventory, and processing sales.
    """

    # Wait between 1-3 seconds between tasks (realistic user behavior)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts. Performs login."""
        self.login()

    def login(self):
        """Authenticate user and get session/token."""
        response = self.client.post(
            "/accounts/login/",
            {"username": f"testuser{random.randint(1, 100)}", "password": "testpass123"},
            catch_response=True,
        )

        if response.status_code == 200 or response.status_code == 302:
            response.success()
        else:
            response.failure(f"Login failed with status {response.status_code}")

    @task(10)
    def view_dashboard(self):
        """View the main dashboard - most common action."""
        with self.client.get("/dashboard/", catch_response=True, name="/dashboard/") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Dashboard failed: {response.status_code}")

    @task(8)
    def view_inventory_list(self):
        """View inventory list with pagination."""
        page = random.randint(1, 5)
        with self.client.get(
            f"/inventory/?page={page}", catch_response=True, name="/inventory/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Inventory list failed: {response.status_code}")

    @task(5)
    def search_inventory(self):
        """Search for inventory items."""
        search_terms = ["gold", "ring", "necklace", "bracelet", "diamond"]
        term = random.choice(search_terms)
        with self.client.get(
            f"/inventory/search/?q={term}", catch_response=True, name="/inventory/search/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Inventory search failed: {response.status_code}")

    @task(3)
    def view_inventory_detail(self):
        """View detailed inventory item."""
        item_id = random.randint(1, 100)
        with self.client.get(
            f"/inventory/{item_id}/", catch_response=True, name="/inventory/[id]/"
        ) as response:
            if response.status_code in [200, 404]:  # 404 is acceptable if item doesn't exist
                response.success()
            else:
                response.failure(f"Inventory detail failed: {response.status_code}")

    @task(2)
    def create_inventory_item(self):
        """Create a new inventory item."""
        product = random.choice(SAMPLE_PRODUCTS)
        data = {
            "name": product["name"],
            "sku": f"{product['sku']}-{random.randint(1000, 9999)}",
            "karat": random.choice([18, 22, 24]),
            "weight_grams": round(random.uniform(5.0, 50.0), 2),
            "cost_price": product["price"] * 0.7,
            "selling_price": product["price"],
            "quantity": random.randint(1, 10),
        }

        with self.client.post(
            "/inventory/create/", data=data, catch_response=True, name="/inventory/create/"
        ) as response:
            if response.status_code in [200, 201, 302]:
                response.success()
            else:
                response.failure(f"Create inventory failed: {response.status_code}")

    @task(7)
    def view_pos_interface(self):
        """View POS interface."""
        with self.client.get("/pos/", catch_response=True, name="/pos/") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"POS interface failed: {response.status_code}")

    @task(4)
    def process_sale(self):
        """Process a sale transaction."""
        product = random.choice(SAMPLE_PRODUCTS)
        customer = random.choice(SAMPLE_CUSTOMERS)

        data = {
            "customer_name": customer["name"],
            "customer_phone": customer["phone"],
            "items": [
                {
                    "product_id": random.randint(1, 100),
                    "quantity": random.randint(1, 3),
                    "price": product["price"],
                }
            ],
            "payment_method": random.choice(["cash", "card", "split"]),
            "total": product["price"] * random.randint(1, 3),
        }

        with self.client.post(
            "/pos/sale/", json=data, catch_response=True, name="/pos/sale/"
        ) as response:
            if response.status_code in [200, 201, 302]:
                response.success()
            else:
                response.failure(f"Process sale failed: {response.status_code}")

    @task(6)
    def view_customers(self):
        """View customer list."""
        page = random.randint(1, 3)
        with self.client.get(
            f"/customers/?page={page}", catch_response=True, name="/customers/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Customer list failed: {response.status_code}")

    @task(3)
    def view_customer_detail(self):
        """View customer detail with purchase history."""
        customer_id = random.randint(1, 50)
        with self.client.get(
            f"/customers/{customer_id}/", catch_response=True, name="/customers/[id]/"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Customer detail failed: {response.status_code}")

    @task(4)
    def view_sales_report(self):
        """View sales reports."""
        report_type = random.choice(["daily", "weekly", "monthly"])
        with self.client.get(
            f"/reports/sales/{report_type}/", catch_response=True, name="/reports/sales/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Sales report failed: {response.status_code}")

    @task(2)
    def view_inventory_report(self):
        """View inventory reports."""
        report_type = random.choice(["valuation", "low-stock", "turnover"])
        with self.client.get(
            f"/reports/inventory/{report_type}/", catch_response=True, name="/reports/inventory/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Inventory report failed: {response.status_code}")

    @task(1)
    def view_accounting(self):
        """View accounting dashboard."""
        with self.client.get("/accounting/", catch_response=True, name="/accounting/") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Accounting failed: {response.status_code}")

    @task(2)
    def api_health_check(self):
        """Check API health endpoint."""
        with self.client.get(
            "/health/ready/", catch_response=True, name="/health/ready/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulates an admin user managing the platform.
    Performs admin tasks like viewing metrics and managing tenants.
    """

    wait_time = between(2, 5)
    weight = 1  # Admin users are less common (10% of total users)

    def on_start(self):
        """Login as admin."""
        self.client.post("/admin/login/", {"username": "admin", "password": "adminpass123"})

    @task(5)
    def view_admin_dashboard(self):
        """View admin dashboard."""
        with self.client.get(
            "/admin/dashboard/", catch_response=True, name="/admin/dashboard/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Admin dashboard failed: {response.status_code}")

    @task(3)
    def view_tenants(self):
        """View tenant list."""
        with self.client.get(
            "/admin/tenants/", catch_response=True, name="/admin/tenants/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Tenant list failed: {response.status_code}")

    @task(2)
    def view_system_metrics(self):
        """View system metrics."""
        with self.client.get(
            "/admin/metrics/", catch_response=True, name="/admin/metrics/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"System metrics failed: {response.status_code}")


# Event handlers for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print(f"\n{'='*80}")
    print(f"LOAD TEST STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {environment.host}")
    print(
        f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}"
    )
    print(f"{'='*80}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print(f"\n{'='*80}")
    print(f"LOAD TEST COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track slow requests."""
    if response_time > 2000:  # Log requests slower than 2 seconds
        print(f"⚠️  SLOW REQUEST: {name} took {response_time}ms")
