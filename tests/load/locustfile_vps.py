"""
Realistic VPS Load Test - Jewelry Shop SaaS Platform

This test simulates realistic production load for a small VPS:
- 4-6GB RAM
- 2-3 CPU cores
- Typical small business usage patterns

Test Scenarios:
1. Light Load (20 users): Normal business hours
2. Medium Load (50 users): Busy hours  
3. Peak Load (100 users): Flash sales/promotions
4. Stress Test (200 users): Find breaking point

Usage:
    # Light load test (10 minutes)
    locust -f tests/load/locustfile_vps.py --host=https://jewelry-shop.local:8443 \
           --users=20 --spawn-rate=2 --run-time=10m --html=reports/vps_light_test.html

    # Medium load test (15 minutes)
    locust -f tests/load/locustfile_vps.py --host=https://jewelry-shop.local:8443 \
           --users=50 --spawn-rate=5 --run-time=15m --html=reports/vps_medium_test.html

    # Peak load test (20 minutes)
    locust -f tests/load/locustfile_vps.py --host=https://jewelry-shop.local:8443 \
           --users=100 --spawn-rate=10 --run-time=20m --html=reports/vps_peak_test.html

    # Stress test - find limits (10 minutes)
    locust -f tests/load/locustfile_vps.py --host=https://jewelry-shop.local:8443 \
           --users=200 --spawn-rate=10 --run-time=10m --html=reports/vps_stress_test.html
"""
import random
from locust import HttpUser, task, between, events


class TenantUser(HttpUser):
    """
    Simulates realistic tenant user behavior on a small jewelry shop.
    Weight: 70% of users (most common - shop staff using POS and inventory)
    """
    weight = 70
    wait_time = between(2, 5)  # More realistic wait time between actions
    
    def on_start(self):
        """Login to tenant portal"""
        self.client.verify = False
        
        response = self.client.post(
            "/accounts/login/",
            data={
                "username": "admin",
                "password": "admin123",
            },
            name="Tenant Login"
        )
    
    @task(15)
    def view_dashboard(self):
        """View dashboard - most frequent action"""
        self.client.get("/dashboard/", name="Dashboard")
    
    @task(10)
    def view_inventory(self):
        """Browse inventory"""
        self.client.get("/inventory/", name="Inventory List")
    
    @task(8)
    def search_inventory(self):
        """Search inventory - common for POS"""
        terms = ["gold", "ring", "necklace", "bracelet", "22k", "18k"]
        term = random.choice(terms)
        self.client.get(f"/inventory/?search={term}", name="Inventory Search")
    
    @task(6)
    def view_sales(self):
        """View sales history"""
        self.client.get("/sales/", name="Sales List")
    
    @task(5)
    def view_customers(self):
        """Browse customers"""
        self.client.get("/crm/customers/", name="Customer List")
    
    @task(3)
    def view_reports(self):
        """View reports"""
        self.client.get("/reports/", name="Reports")
    
    @task(2)
    def create_sale(self):
        """POS sale - less frequent but important"""
        sale_data = {
            "customer": random.randint(1, 50),
            "items": [
                {
                    "product_id": random.randint(1, 30),
                    "quantity": 1,
                    "price": random.uniform(500, 3000)
                }
            ],
            "payment_method": random.choice(["cash", "card"]),
        }
        
        self.client.post("/api/sales/", json=sale_data, name="Create Sale")


class PlatformAdminUser(HttpUser):
    """
    Platform admin checking system health and managing tenants.
    Weight: 5% (very few admin users)
    """
    weight = 5
    wait_time = between(5, 10)  # Admins take more time between actions
    
    def on_start(self):
        """Login to platform admin"""
        self.client.verify = False
        
        self.client.post(
            "/platform/login/",
            data={
                "username": "platformadmin",
                "password": "PlatformAdmin123!",
            },
            name="Platform Login"
        )
    
    @task(10)
    def view_dashboard(self):
        """Admin dashboard"""
        self.client.get("/platform/dashboard/", name="Platform Dashboard")
    
    @task(5)
    def view_tenants(self):
        """View tenants"""
        self.client.get("/platform/tenants/", name="Tenant List")
    
    @task(3)
    def view_monitoring(self):
        """Check system health"""
        self.client.get("/platform/monitoring/", name="System Health")


class APIUser(HttpUser):
    """
    API users (mobile app, integrations, external systems).
    Weight: 25% (external integrations and API calls)
    """
    weight = 25
    wait_time = between(1, 3)  # API calls are faster
    
    def on_start(self):
        """Get API token"""
        self.client.verify = False
        
        response = self.client.post(
            "/api/token/",
            json={
                "username": "admin",
                "password": "admin123"
            },
            name="API Token"
        )
        
        if response.status_code == 200:
            self.token = response.json().get("access")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    @task(12)
    def api_inventory(self):
        """List inventory via API"""
        self.client.get(
            "/api/inventory/",
            headers=self.headers,
            name="API Inventory"
        )
    
    @task(8)
    def api_customers(self):
        """List customers via API"""
        self.client.get(
            "/api/crm/customers/",
            headers=self.headers,
            name="API Customers"
        )
    
    @task(6)
    def api_sales(self):
        """List sales via API"""
        self.client.get(
            "/api/sales/",
            headers=self.headers,
            name="API Sales"
        )
    
    @task(3)
    def api_create_customer(self):
        """Create customer via API"""
        customer_data = {
            "name": f"Customer {random.randint(1000, 9999)}",
            "email": f"customer{random.randint(1000, 9999)}@example.com",
            "phone": f"+1555{random.randint(1000000, 9999999)}"
        }
        
        self.client.post(
            "/api/crm/customers/",
            json=customer_data,
            headers=self.headers,
            name="API Create Customer"
        )


# Event handlers for metrics and reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start notification"""
    print("=" * 80)
    print("VPS LOAD TEST STARTING")
    print("=" * 80)
    print(f"Target: {environment.host}")
    print("Simulating small business jewelry shop usage")
    print("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test completion with performance summary"""
    print("\n" + "=" * 80)
    print("VPS LOAD TEST COMPLETED")
    print("=" * 80)
    
    stats = environment.stats
    total = stats.total
    
    print(f"\n📊 PERFORMANCE SUMMARY:")
    print(f"   Total Requests: {total.num_requests:,}")
    print(f"   Failed Requests: {total.num_failures:,}")
    print(f"   Failure Rate: {total.fail_ratio * 100:.2f}%")
    print(f"   Average Response Time: {total.avg_response_time:.0f}ms")
    print(f"   Median Response Time: {total.get_response_time_percentile(0.5):.0f}ms")
    print(f"   95th Percentile: {total.get_response_time_percentile(0.95):.0f}ms")
    print(f"   99th Percentile: {total.get_response_time_percentile(0.99):.0f}ms")
    print(f"   Max Response Time: {total.max_response_time:.0f}ms")
    print(f"   Requests/sec: {total.total_rps:.2f}")
    
    print(f"\n🎯 VPS PERFORMANCE ASSESSMENT:")
    
    # Assess response times
    p95 = total.get_response_time_percentile(0.95)
    p99 = total.get_response_time_percentile(0.99)
    
    if p95 < 1000:
        print(f"   ✅ Excellent: p95 = {p95:.0f}ms (< 1000ms)")
    elif p95 < 2000:
        print(f"   ✅ Good: p95 = {p95:.0f}ms (< 2000ms)")
    elif p95 < 3000:
        print(f"   ⚠️  Acceptable: p95 = {p95:.0f}ms (< 3000ms)")
    else:
        print(f"   ❌ Poor: p95 = {p95:.0f}ms (> 3000ms)")
    
    # Assess error rate
    if total.fail_ratio < 0.01:
        print(f"   ✅ Excellent: Error rate = {total.fail_ratio * 100:.2f}% (< 1%)")
    elif total.fail_ratio < 0.05:
        print(f"   ⚠️  Acceptable: Error rate = {total.fail_ratio * 100:.2f}% (< 5%)")
    else:
        print(f"   ❌ Poor: Error rate = {total.fail_ratio * 100:.2f}% (> 5%)")
    
    # Assess throughput
    if total.total_rps > 50:
        print(f"   ✅ Good throughput: {total.total_rps:.1f} req/s")
    elif total.total_rps > 20:
        print(f"   ⚠️  Moderate throughput: {total.total_rps:.1f} req/s")
    else:
        print(f"   ❌ Low throughput: {total.total_rps:.1f} req/s")
    
    print("\n💡 RECOMMENDATIONS:")
    
    if total.fail_ratio > 0.05:
        print("   ⚠️  High error rate - consider:")
        print("      - Increasing resource limits")
        print("      - Adding more replicas")
        print("      - Upgrading VPS")
    
    if p95 > 2000:
        print("   ⚠️  Slow response times - consider:")
        print("      - Database query optimization")
        print("      - Adding caching")
        print("      - Upgrading VPS CPU")
    
    if total.total_rps < 20:
        print("   ⚠️  Low throughput - consider:")
        print("      - Increasing gunicorn workers")
        print("      - Scaling horizontally")
        print("      - Checking for bottlenecks")
    
    # VPS sizing recommendation
    users = environment.runner.user_count if hasattr(environment.runner, 'user_count') else 0
    
    print(f"\n📈 VPS SIZING RECOMMENDATION for {users} concurrent users:")
    
    if users <= 20 and p95 < 2000 and total.fail_ratio < 0.05:
        print("   ✅ 4GB RAM / 2 CPU sufficient for light load")
    elif users <= 50 and p95 < 2000 and total.fail_ratio < 0.05:
        print("   ✅ 4GB RAM / 2 CPU can handle medium load")
    elif users <= 100:
        if p95 < 2000 and total.fail_ratio < 0.05:
            print("   ✅ Current VPS can handle peak load")
        else:
            print("   ⚠️  Consider upgrading to 6GB RAM / 3 CPU for peak load")
    else:
        print("   ⚠️  For >100 users, upgrade to 8GB+ RAM / 4+ CPU")
    
    print("=" * 80)
