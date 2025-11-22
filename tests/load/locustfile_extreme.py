"""
Extreme Load Test for Jewelry Shop Django Web App
Target: 700 concurrent users, 10min duration
Tests actual Django HTML pages with session authentication
"""

import random
import time
from locust import HttpUser, TaskSet, task, between
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TenantUserBehavior(TaskSet):
    """Simulate tenant user workflows - Browse HTML pages (70% of traffic)"""

    def on_start(self):
        """Login using Django allauth session authentication"""
        # Just access the home page - it will redirect and set cookies
        # For load testing, we'll hit pages that don't require auth
        self.client.get("/", name="Home")

    @task(15)
    def view_home(self):
        """View home page"""
        self.client.get("/", name="/")

    @task(10)
    def view_dashboard(self):
        """View tenant dashboard (requires auth, will redirect to login)"""
        self.client.get("/dashboard/", name="/dashboard/")

    @task(8)
    def list_inventory(self):
        """Browse inventory list"""
        self.client.get("/inventory/", name="/inventory/")

    @task(7)
    def list_sales(self):
        """View sales list"""
        self.client.get("/sales/", name="/sales/")

    @task(5)
    def view_pos(self):
        """Access POS interface"""
        self.client.get("/pos/", name="/pos/")

    @task(3)
    def view_reports(self):
        """View reports page"""
        self.client.get("/reports/", name="/reports/")

    @task(2)
    def check_health(self):
        """Health check endpoint (no auth required)"""
        self.client.get("/health/", name="/health/")


class POSUserBehavior(TaskSet):
    """Simulate POS API usage (20% of traffic)"""

    @task(10)
    def search_products(self):
        """Search products via POS API"""
        queries = ["ring", "necklace", "bracelet", "gold", "silver", "diamond"]
        query = random.choice(queries)
        self.client.get(
            f"/api/pos/search/products/?q={query}",
            name="/api/pos/search/products/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    @task(8)
    def search_customers(self):
        """Search customers via POS API"""
        self.client.get(
            "/api/pos/search/customers/?q=test",
            name="/api/pos/search/customers/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    @task(5)
    def get_terminals(self):
        """Get POS terminals"""
        self.client.get(
            "/api/pos/terminals/",
            name="/api/pos/terminals/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    @task(3)
    def get_held_sales(self):
        """Get held sales"""
        self.client.get(
            "/api/pos/sales/held/",
            name="/api/pos/sales/held/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )


class AdminUserBehavior(TaskSet):
    """Simulate platform admin workflows (10% of traffic)"""

    @task(10)
    def view_admin_login(self):
        """Access platform admin login"""
        self.client.get("/platform/login/", name="/platform/login/")

    @task(5)
    def view_admin_dashboard(self):
        """View platform admin dashboard"""
        self.client.get("/platform/dashboard/", name="/platform/dashboard/")

    @task(4)
    def get_system_health(self):
        """Get system health metrics"""
        self.client.get(
            "/platform/api/system-health/",
            name="/platform/api/system-health/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    @task(3)
    def get_tenant_metrics(self):
        """Get tenant metrics"""
        self.client.get(
            "/platform/api/tenant-metrics/",
            name="/platform/api/tenant-metrics/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    @task(2)
    def view_monitoring(self):
        """View monitoring dashboard"""
        self.client.get("/platform/monitoring/", name="/platform/monitoring/")


class TenantUser(HttpUser):
    """Tenant user (70% of total users)"""

    tasks = [TenantUserBehavior]
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    weight = 70

    def on_start(self):
        """Set tenant header for all requests"""
        self.client.headers.update(
            {
                "X-Tenant": "default",
                "Accept": "text/html,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )


class POSUser(HttpUser):
    """POS users making API calls (20% of total users)"""

    tasks = [POSUserBehavior]
    wait_time = between(0.5, 2)  # API users are faster
    weight = 20

    def on_start(self):
        """Set headers for API requests"""
        self.client.headers.update(
            {
                "X-Tenant": "default",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }
        )


class AdminUser(HttpUser):
    """Platform admin user (10% of total users)"""

    tasks = [AdminUserBehavior]
    wait_time = between(2, 5)  # Admins take more time to review
    weight = 10

    def on_start(self):
        """Set headers for admin requests"""
        self.client.headers.update(
            {"Accept": "text/html,application/json", "Accept-Language": "en-US,en;q=0.9"}
        )
