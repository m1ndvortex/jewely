"""
Tests for CRM views and customer management interface.

Implements Requirement 12: Customer Relationship Management (CRM)
- Test customer list view with search and filters
- Test customer profile view with purchase history
- Test customer create/edit forms
- Test customer communication history logging
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls, set_tenant_context
from apps.crm.models import Customer, CustomerCommunication, LoyaltyTier

User = get_user_model()


@pytest.fixture(scope="function")
def crm_tenant(db):
    """Create a test tenant for CRM views."""
    with bypass_rls():
        tenant = Tenant.objects.create(
            company_name="Test CRM Jewelry Shop", slug="test-crm-views-shop", status="ACTIVE"
        )
    yield tenant
    # Cleanup
    with bypass_rls():
        tenant.delete()


@pytest.fixture(scope="function")
def crm_branch(crm_tenant):
    """Create a test branch."""
    with bypass_rls():
        branch = Branch.objects.create(
            tenant=crm_tenant, name="Main Branch", address="123 Main St", phone="+1234567890"
        )
    return branch


@pytest.fixture(scope="function")
def crm_user(crm_tenant):
    """Create a test user."""
    with bypass_rls():
        user = User.objects.create_user(
            username="testcrmuser",
            email="testcrm@example.com",
            password="testpass123",
            tenant=crm_tenant,
            role="TENANT_OWNER",
        )
    return user


@pytest.fixture(scope="function")
def crm_bronze_tier(crm_tenant):
    """Create bronze loyalty tier."""
    with bypass_rls():
        tier = LoyaltyTier.objects.create(
            tenant=crm_tenant,
            name="Bronze",
            min_spending=Decimal("0.00"),
            discount_percentage=Decimal("5.00"),
            points_multiplier=Decimal("1.0"),
            order=0,
        )
    return tier


@pytest.fixture(scope="function")
def crm_silver_tier(crm_tenant):
    """Create silver loyalty tier."""
    with bypass_rls():
        tier = LoyaltyTier.objects.create(
            tenant=crm_tenant,
            name="Silver",
            min_spending=Decimal("500.00"),
            discount_percentage=Decimal("10.00"),
            points_multiplier=Decimal("1.5"),
            order=1,
        )
    return tier


@pytest.fixture(scope="function")
def crm_customer1(crm_tenant, crm_bronze_tier):
    """Create test customer 1."""
    with bypass_rls():
        customer = Customer.objects.create(
            tenant=crm_tenant,
            customer_number="CUST-001",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+1234567890",
            loyalty_tier=crm_bronze_tier,
            loyalty_points=100,
            total_purchases=Decimal("250.00"),
            is_active=True,
        )
    return customer


@pytest.fixture(scope="function")
def crm_customer2(crm_tenant, crm_silver_tier):
    """Create test customer 2."""
    with bypass_rls():
        customer = Customer.objects.create(
            tenant=crm_tenant,
            customer_number="CUST-002",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+0987654321",
            loyalty_tier=crm_silver_tier,
            loyalty_points=500,
            total_purchases=Decimal("750.00"),
            is_active=True,
            tags=["VIP", "Wedding"],
        )
    return customer


@pytest.fixture(scope="function")
def crm_customer3(crm_tenant):
    """Create test customer 3."""
    with bypass_rls():
        customer = Customer.objects.create(
            tenant=crm_tenant,
            customer_number="CUST-003",
            first_name="Bob",
            last_name="Wilson",
            phone="+1122334455",
            is_active=False,
        )
    return customer


@pytest.fixture(scope="function")
def crm_authenticated_client(crm_user, crm_tenant):
    """Create an authenticated client with tenant context."""
    client = Client()
    # Set tenant context before login
    set_tenant_context(crm_tenant.id)
    client.force_login(crm_user)
    return client


@pytest.mark.django_db
class TestCustomerManagementViews:
    """Test customer management interface views."""

    def test_customer_list_view(
        self, crm_authenticated_client, crm_customer1, crm_customer2, crm_customer3
    ):
        """Test customer list view loads successfully."""
        response = crm_authenticated_client.get(reverse("crm:customer_list"))

        assert response.status_code == 200
        assert "customers" in response.context
        assert len(response.context["customers"]) >= 3

    def test_customer_list_search(self, crm_authenticated_client, crm_customer1, crm_customer2):
        """Test customer list search functionality."""
        response = crm_authenticated_client.get(reverse("crm:customer_list"), {"q": "John"})

        assert response.status_code == 200
        customers = response.context["customers"]
        assert any(c.first_name == "John" for c in customers)

    def test_customer_list_filter_by_tier(
        self, crm_authenticated_client, crm_customer1, crm_customer2, crm_silver_tier
    ):
        """Test customer list filter by loyalty tier."""
        response = crm_authenticated_client.get(
            reverse("crm:customer_list"), {"tier": str(crm_silver_tier.id)}
        )

        assert response.status_code == 200
        customers = list(response.context["customers"])
        assert all(c.loyalty_tier == crm_silver_tier for c in customers if c.loyalty_tier)

    def test_customer_list_filter_by_status(
        self, crm_authenticated_client, crm_customer1, crm_customer2, crm_customer3
    ):
        """Test customer list filter by active status."""
        response = crm_authenticated_client.get(reverse("crm:customer_list"), {"status": "active"})

        assert response.status_code == 200
        customers = list(response.context["customers"])
        assert all(c.is_active for c in customers)

    def test_customer_list_filter_by_tag(
        self, crm_authenticated_client, crm_customer1, crm_customer2
    ):
        """Test customer list filter by tag."""
        response = crm_authenticated_client.get(reverse("crm:customer_list"), {"tag": "VIP"})

        assert response.status_code == 200
        customers = list(response.context["customers"])
        assert any("VIP" in c.tags for c in customers if c.tags)

    def test_customer_detail_view(self, crm_authenticated_client, crm_customer1):
        """Test customer detail view loads successfully."""
        response = crm_authenticated_client.get(
            reverse("crm:customer_detail", args=[crm_customer1.id])
        )

        assert response.status_code == 200
        assert response.context["customer"] == crm_customer1
        assert "purchases" in response.context
        assert "loyalty_transactions" in response.context
        assert "communications" in response.context

    def test_customer_create_view_get(self, crm_authenticated_client):
        """Test customer create form loads successfully."""
        response = crm_authenticated_client.get(reverse("crm:customer_create"))

        assert response.status_code == 200
        assert "loyalty_tiers" in response.context

    def test_customer_create_view_post(self, crm_authenticated_client, crm_tenant):
        """Test customer creation via form submission."""
        data = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "phone": "+1555666777",
            "email": "alice@example.com",
            "preferred_communication": "EMAIL",
            "marketing_opt_in": "on",
        }

        response = crm_authenticated_client.post(reverse("crm:customer_create"), data)

        # Should redirect to customer detail page
        assert response.status_code == 302

        # Verify customer was created
        with bypass_rls():
            customer = Customer.objects.filter(
                tenant=crm_tenant, first_name="Alice", last_name="Johnson"
            ).first()
            assert customer is not None
            assert customer.email == "alice@example.com"
            assert customer.phone == "+1555666777"
            assert customer.marketing_opt_in is True

    def test_customer_edit_view_get(self, crm_authenticated_client, crm_customer1):
        """Test customer edit form loads successfully."""
        response = crm_authenticated_client.get(
            reverse("crm:customer_edit", args=[crm_customer1.id])
        )

        assert response.status_code == 200
        assert response.context["customer"] == crm_customer1
        assert response.context["is_edit"] is True

    def test_customer_edit_view_post(self, crm_authenticated_client, crm_customer1):
        """Test customer update via form submission."""
        data = {
            "first_name": "John",
            "last_name": "Doe Updated",
            "phone": "+1234567890",
            "email": "john.updated@example.com",
            "preferred_communication": "SMS",
            "marketing_opt_in": "on",
            "sms_opt_in": "on",
        }

        response = crm_authenticated_client.post(
            reverse("crm:customer_edit", args=[crm_customer1.id]), data
        )

        # Should redirect to customer detail page
        assert response.status_code == 302

        # Verify customer was updated
        with bypass_rls():
            customer = Customer.objects.get(id=crm_customer1.id)
            assert customer.last_name == "Doe Updated"
            assert customer.email == "john.updated@example.com"
            assert customer.preferred_communication == "SMS"
            assert customer.sms_opt_in is True

    def test_customer_communication_add(self, crm_authenticated_client, crm_customer1, crm_user):
        """Test adding communication record for customer."""
        data = {
            "communication_type": "NOTE",
            "direction": "OUTBOUND",
            "subject": "Follow-up call",
            "content": "Called customer to discuss new products",
            "duration_minutes": "15",
        }

        response = crm_authenticated_client.post(
            reverse("crm:customer_communication_add", args=[crm_customer1.id]), data
        )

        assert response.status_code == 200

        # Verify communication was created
        with bypass_rls():
            comm = CustomerCommunication.objects.filter(
                customer=crm_customer1, subject="Follow-up call"
            ).first()
            assert comm is not None
            assert comm.communication_type == "NOTE"
            assert comm.content == "Called customer to discuss new products"
            assert comm.duration_minutes == 15
            assert comm.created_by == crm_user

    def test_customer_list_requires_authentication(self):
        """Test customer list requires authentication."""
        client = Client()
        response = client.get(reverse("crm:customer_list"))

        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_customer_detail_requires_authentication(self, crm_customer1):
        """Test customer detail requires authentication."""
        client = Client()
        response = client.get(reverse("crm:customer_detail", args=[crm_customer1.id]))

        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
