"""
Integration tests for tenant management interface (Task 16.1).

Tests all acceptance criteria from Requirement 4:
1. Create new tenant accounts manually
2. Search and filter capabilities (status, subscription plan, registration date)
3. Modify tenant information
4. Change tenant status (Active, Suspended, Scheduled for Deletion)
5. Secure tenant impersonation with audit trail (placeholder for Task 19)
6. Prevent viewing/setting passwords directly
7. Initiate password resets (placeholder for Task 19)
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.models import Branch, Tenant, User
from apps.core.tenant_context import bypass_rls


def create_tenant(**kwargs):
    """Helper function to create tenants with RLS bypass."""
    with bypass_rls():
        return Tenant.objects.create(**kwargs)


def create_user(**kwargs):
    """Helper function to create users with RLS bypass."""
    with bypass_rls():
        return User.objects.create_user(**kwargs)


def create_branch(**kwargs):
    """Helper function to create branches with RLS bypass."""
    with bypass_rls():
        return Branch.objects.create(**kwargs)


@pytest.mark.django_db
class TestTenantListView:
    """Test tenant list view with search and filters."""

    def test_tenant_list_requires_authentication(self, client):
        """Test that tenant list requires authentication."""
        url = reverse("core:admin_tenant_list")
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response.url or "login" in response.url.lower()

    def test_tenant_list_requires_platform_admin(self, client, tenant_owner):
        """Test that tenant list requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_list")
        response = client.get(url)

        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_tenant_list_accessible_by_platform_admin(self, client, platform_admin):
        """Test that platform admin can access tenant list."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url)

        assert response.status_code == 200
        assert "tenants" in response.context

    def test_tenant_list_displays_all_tenants(self, client, platform_admin):
        """Test that tenant list displays all tenants."""
        # Create multiple tenants
        tenant1 = create_tenant(company_name="Shop A", slug="shop-a")
        tenant2 = create_tenant(company_name="Shop B", slug="shop-b")
        tenant3 = create_tenant(company_name="Shop C", slug="shop-c")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url)

        assert response.status_code == 200
        tenants = response.context["tenants"]
        assert tenant1 in tenants
        assert tenant2 in tenants
        assert tenant3 in tenants

    def test_tenant_list_search_by_company_name(self, client, platform_admin):
        """Test searching tenants by company name."""
        tenant1 = create_tenant(company_name="Golden Jewelry", slug="golden-jewelry")
        tenant2 = create_tenant(company_name="Silver Shop", slug="silver-shop")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url, {"search": "Golden"})

        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert tenant1 in tenants
        assert tenant2 not in tenants

    def test_tenant_list_search_by_slug(self, client, platform_admin):
        """Test searching tenants by slug."""
        tenant1 = create_tenant(company_name="Shop A", slug="shop-a")
        tenant2 = create_tenant(company_name="Shop B", slug="shop-b")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url, {"search": "shop-a"})

        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert tenant1 in tenants
        assert tenant2 not in tenants

    def test_tenant_list_filter_by_status(self, client, platform_admin):
        """Test filtering tenants by status."""
        tenant1 = create_tenant(
            company_name="Active Shop", slug="active-shop", status=Tenant.ACTIVE
        )
        tenant2 = create_tenant(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url, {"status": Tenant.ACTIVE})

        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert tenant1 in tenants
        assert tenant2 not in tenants

    def test_tenant_list_filter_by_date_range(self, client, platform_admin):
        """Test filtering tenants by registration date range."""
        # Create tenants with different dates
        old_date = timezone.now() - timedelta(days=60)
        recent_date = timezone.now() - timedelta(days=5)

        tenant1 = create_tenant(company_name="Old Shop", slug="old-shop")
        with bypass_rls():
            tenant1.created_at = old_date
            tenant1.save()

        tenant2 = create_tenant(company_name="Recent Shop", slug="recent-shop")
        with bypass_rls():
            tenant2.created_at = recent_date
            tenant2.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")

        # Filter for last 30 days
        date_from = (timezone.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        response = client.get(url, {"date_from": date_from})

        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert tenant2 in tenants
        assert tenant1 not in tenants

    def test_tenant_list_displays_statistics(self, client, platform_admin):
        """Test that tenant list displays statistics."""
        create_tenant(company_name="Active 1", slug="active-1", status=Tenant.ACTIVE)
        create_tenant(company_name="Active 2", slug="active-2", status=Tenant.ACTIVE)
        create_tenant(company_name="Suspended", slug="suspended", status=Tenant.SUSPENDED)
        create_tenant(company_name="Pending", slug="pending", status=Tenant.PENDING_DELETION)

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")
        response = client.get(url)

        assert response.status_code == 200
        # Check that at least the tenants we created are counted
        assert response.context["total_tenants"] >= 4
        assert response.context["active_tenants"] >= 2
        assert response.context["suspended_tenants"] >= 1
        assert response.context["pending_deletion_tenants"] >= 1


@pytest.mark.django_db
class TestTenantDetailView:
    """Test tenant detail view."""

    def test_tenant_detail_requires_authentication(self, client, tenant):
        """Test that tenant detail requires authentication."""
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 302

    def test_tenant_detail_requires_platform_admin(self, client, tenant, tenant_owner):
        """Test that tenant detail requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 403

    def test_tenant_detail_displays_basic_info(self, client, platform_admin, tenant):
        """Test that tenant detail displays basic information."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["tenant"] == tenant
        assert tenant.company_name in response.content.decode()
        assert tenant.slug in response.content.decode()

    def test_tenant_detail_displays_users(self, client, platform_admin, tenant):
        """Test that tenant detail displays tenant users."""
        # Create users for the tenant
        user1 = create_user(
            username="user1", email="user1@test.com", tenant=tenant, role=User.TENANT_OWNER
        )
        user2 = create_user(
            username="user2", email="user2@test.com", tenant=tenant, role=User.TENANT_EMPLOYEE
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url, {"tab": "users"})

        assert response.status_code == 200
        assert response.context["user_count"] == 2
        users = list(response.context["users"])
        assert user1 in users
        assert user2 in users

    def test_tenant_detail_displays_branches(self, client, platform_admin, tenant):
        """Test that tenant detail displays tenant branches."""
        create_branch(tenant=tenant, name="Main Branch")
        create_branch(tenant=tenant, name="Second Branch")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["branch_count"] == 2


@pytest.mark.django_db
class TestTenantCreateView:
    """Test tenant creation."""

    def test_tenant_create_requires_authentication(self, client):
        """Test that tenant creation requires authentication."""
        url = reverse("core:admin_tenant_create")
        response = client.get(url)

        assert response.status_code == 302

    def test_tenant_create_requires_platform_admin(self, client, tenant_owner):
        """Test that tenant creation requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_create")
        response = client.get(url)

        assert response.status_code == 403

    def test_tenant_create_form_displays(self, client, platform_admin):
        """Test that tenant creation form displays."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_create")
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context

    def test_tenant_create_with_valid_data(self, client, platform_admin):
        """Test creating a tenant with valid data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_create")

        data = {
            "company_name": "New Jewelry Shop",
            "slug": "new-jewelry-shop",
            "status": Tenant.ACTIVE,
        }

        response = client.post(url, data)

        # Should redirect to tenant list
        assert response.status_code == 302
        assert response.url == reverse("core:admin_tenant_list")

        # Verify tenant was created
        with bypass_rls():
            tenant = Tenant.objects.get(slug="new-jewelry-shop")
            assert tenant.company_name == "New Jewelry Shop"
            assert tenant.status == Tenant.ACTIVE

    def test_tenant_create_auto_generates_slug(self, client, platform_admin):
        """Test that slug is auto-generated if not provided."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_create")

        data = {"company_name": "Auto Slug Shop", "slug": "", "status": Tenant.ACTIVE}  # Empty slug

        response = client.post(url, data)

        assert response.status_code == 302

        # Verify tenant was created with auto-generated slug
        with bypass_rls():
            tenant = Tenant.objects.get(company_name="Auto Slug Shop")
            assert tenant.slug == "auto-slug-shop"

    def test_tenant_create_validates_duplicate_slug(self, client, platform_admin):
        """Test that duplicate slugs are rejected."""
        # Create existing tenant
        create_tenant(company_name="Existing", slug="existing-shop")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_create")

        data = {
            "company_name": "New Shop",
            "slug": "existing-shop",  # Duplicate slug
            "status": Tenant.ACTIVE,
        }

        response = client.post(url, data)

        # Should not redirect (form has errors)
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors


@pytest.mark.django_db
class TestTenantUpdateView:
    """Test tenant update."""

    def test_tenant_update_requires_authentication(self, client, tenant):
        """Test that tenant update requires authentication."""
        url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 302

    def test_tenant_update_requires_platform_admin(self, client, tenant, tenant_owner):
        """Test that tenant update requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 403

    def test_tenant_update_form_displays(self, client, platform_admin, tenant):
        """Test that tenant update form displays."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["tenant"] == tenant

    def test_tenant_update_with_valid_data(self, client, platform_admin, tenant):
        """Test updating a tenant with valid data."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})

        data = {
            "company_name": "Updated Shop Name",
            "slug": tenant.slug,
            "status": Tenant.SUSPENDED,
        }

        response = client.post(url, data)

        # Should redirect to tenant detail
        assert response.status_code == 302
        assert response.url == reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})

        # Verify tenant was updated
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.company_name == "Updated Shop Name"
            assert tenant.status == Tenant.SUSPENDED

    def test_tenant_update_validates_duplicate_slug(self, client, platform_admin, tenant):
        """Test that duplicate slugs are rejected during update."""
        # Create another tenant
        create_tenant(company_name="Other", slug="other-shop")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})

        data = {
            "company_name": tenant.company_name,
            "slug": "other-shop",  # Duplicate slug
            "status": tenant.status,
        }

        response = client.post(url, data)

        # Should not redirect (form has errors)
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors


@pytest.mark.django_db
class TestTenantStatusChange:
    """Test tenant status changes."""

    def test_status_change_requires_authentication(self, client, tenant):
        """Test that status change requires authentication."""
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.SUSPENDED})

        assert response.status_code == 302

    def test_status_change_requires_platform_admin(self, client, tenant, tenant_owner):
        """Test that status change requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.SUSPENDED})

        assert response.status_code == 403

    def test_status_change_to_suspended(self, client, platform_admin, tenant):
        """Test changing tenant status to suspended."""
        assert tenant.status == Tenant.ACTIVE

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.SUSPENDED})

        # Should redirect to tenant detail
        assert response.status_code == 302

        # Verify status was changed
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.SUSPENDED

    def test_status_change_to_pending_deletion(self, client, platform_admin, tenant):
        """Test changing tenant status to pending deletion."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.PENDING_DELETION})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.PENDING_DELETION

    def test_status_change_to_active(self, client, platform_admin):
        """Test reactivating a suspended tenant."""
        tenant = create_tenant(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.ACTIVE})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE

    def test_status_change_rejects_invalid_status(self, client, platform_admin, tenant):
        """Test that invalid status values are rejected."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": "INVALID_STATUS"})

        # Should redirect with error message
        assert response.status_code == 302

        # Status should not change
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE


@pytest.mark.django_db
class TestTenantDelete:
    """Test tenant deletion."""

    def test_tenant_delete_requires_authentication(self, client, tenant):
        """Test that tenant deletion requires authentication."""
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 302

    def test_tenant_delete_requires_platform_admin(self, client, tenant, tenant_owner):
        """Test that tenant deletion requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 403

    def test_tenant_delete_confirmation_page(self, client, platform_admin, tenant):
        """Test that delete confirmation page displays."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert "tenant" in response.context
        assert tenant.company_name in response.content.decode()

    def test_tenant_delete_shows_related_data_count(self, client, platform_admin, tenant):
        """Test that delete page shows count of related data."""
        # Create related data
        create_user(username="user1", email="user1@test.com", tenant=tenant, role=User.TENANT_OWNER)
        create_branch(tenant=tenant, name="Branch 1")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["user_count"] == 1
        assert response.context["branch_count"] == 1

    def test_tenant_delete_permanently_removes_tenant(self, client, platform_admin, tenant):
        """Test that tenant is permanently deleted."""
        tenant_id = tenant.pk

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.post(url)

        # Should redirect to tenant list
        assert response.status_code == 302
        assert response.url == reverse("core:admin_tenant_list")

        # Verify tenant was deleted
        assert not Tenant.objects.filter(pk=tenant_id).exists()

    def test_tenant_delete_cascades_to_users(self, client, platform_admin, tenant):
        """Test that deleting tenant also deletes users."""
        user = create_user(
            username="user1", email="user1@test.com", tenant=tenant, role=User.TENANT_OWNER
        )
        user_id = user.pk

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.post(url)

        assert response.status_code == 302

        # Verify user was deleted
        assert not User.objects.filter(pk=user_id).exists()

    def test_tenant_delete_cascades_to_branches(self, client, platform_admin, tenant):
        """Test that deleting tenant also deletes branches."""
        branch = create_branch(tenant=tenant, name="Branch 1")
        branch_id = branch.pk

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.post(url)

        assert response.status_code == 302

        # Verify branch was deleted
        assert not Branch.objects.filter(pk=branch_id).exists()


@pytest.mark.django_db
class TestTenantManagementIntegration:
    """Integration tests for complete tenant management workflows."""

    def test_complete_tenant_lifecycle(self, client, platform_admin):
        """Test complete tenant lifecycle: create, update, suspend, delete."""
        client.force_login(platform_admin)

        # 1. Create tenant
        create_url = reverse("core:admin_tenant_create")
        create_data = {
            "company_name": "Lifecycle Test Shop",
            "slug": "lifecycle-test",
            "status": Tenant.ACTIVE,
        }
        response = client.post(create_url, create_data)
        assert response.status_code == 302

        with bypass_rls():
            tenant = Tenant.objects.get(slug="lifecycle-test")
            assert tenant.status == Tenant.ACTIVE

        # 2. Update tenant
        update_url = reverse("core:admin_tenant_update", kwargs={"pk": tenant.pk})
        update_data = {
            "company_name": "Updated Lifecycle Shop",
            "slug": "lifecycle-test",
            "status": Tenant.ACTIVE,
        }
        response = client.post(update_url, update_data)
        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.company_name == "Updated Lifecycle Shop"

        # 3. Suspend tenant
        status_url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(status_url, {"status": Tenant.SUSPENDED})
        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.SUSPENDED

        # 4. Mark for deletion
        response = client.post(status_url, {"status": Tenant.PENDING_DELETION})
        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.PENDING_DELETION

        # 5. Delete tenant
        delete_url = reverse("core:admin_tenant_delete", kwargs={"pk": tenant.pk})
        response = client.post(delete_url)
        assert response.status_code == 302

        with bypass_rls():
            assert not Tenant.objects.filter(pk=tenant.pk).exists()

    def test_tenant_with_users_and_branches(self, client, platform_admin):
        """Test managing tenant with users and branches."""
        client.force_login(platform_admin)

        # Create tenant
        tenant = create_tenant(
            company_name="Full Test Shop", slug="full-test", status=Tenant.ACTIVE
        )

        # Add users
        user1 = create_user(
            username="owner", email="owner@test.com", tenant=tenant, role=User.TENANT_OWNER
        )
        user2 = create_user(
            username="employee", email="employee@test.com", tenant=tenant, role=User.TENANT_EMPLOYEE
        )

        # Add branches
        create_branch(tenant=tenant, name="Main Branch")
        create_branch(tenant=tenant, name="Second Branch")

        # View tenant detail
        detail_url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(detail_url)
        assert response.status_code == 200
        assert response.context["user_count"] == 2
        assert response.context["branch_count"] == 2

        # View users tab
        response = client.get(detail_url, {"tab": "users"})
        assert response.status_code == 200
        users = list(response.context["users"])
        assert user1 in users
        assert user2 in users

    def test_search_and_filter_combination(self, client, platform_admin):
        """Test combining search and filters."""
        # Create test tenants
        create_tenant(company_name="Gold Shop Active", slug="gold-active", status=Tenant.ACTIVE)
        create_tenant(
            company_name="Gold Shop Suspended", slug="gold-suspended", status=Tenant.SUSPENDED
        )
        create_tenant(company_name="Silver Shop Active", slug="silver-active", status=Tenant.ACTIVE)

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_list")

        # Search for "Gold" and filter by ACTIVE status
        response = client.get(url, {"search": "Gold", "status": Tenant.ACTIVE})

        assert response.status_code == 200
        tenants = list(response.context["tenants"])
        assert len(tenants) == 1
        assert tenants[0].slug == "gold-active"


@pytest.mark.django_db
class TestTenantStatusManagement:
    """
    Tests for Task 16.2: Tenant Status Management

    Tests all sub-tasks:
    1. Status change interface with confirmation modal
    2. Suspend tenant functionality (disable access, retain data)
    3. Schedule for deletion with grace period
    4. Tenant reactivation functionality
    """

    def test_suspend_tenant_sets_suspended_at_timestamp(self, client, platform_admin, tenant):
        """Test that suspending a tenant sets the suspended_at timestamp."""
        with bypass_rls():
            assert tenant.suspended_at is None

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.SUSPENDED, "reason": "Payment overdue"})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.SUSPENDED
            assert tenant.suspended_at is not None
            assert tenant.suspended_at <= timezone.now()

    def test_suspend_tenant_retains_data(self, client, platform_admin, tenant):
        """Test that suspending a tenant retains all data."""
        # Create related data
        user = create_user(
            username="testuser", email="test@test.com", tenant=tenant, role=User.TENANT_OWNER
        )
        branch = create_branch(tenant=tenant, name="Test Branch")

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.SUSPENDED})

        assert response.status_code == 302

        # Verify data is retained
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.SUSPENDED
            assert User.objects.filter(pk=user.pk).exists()
            assert Branch.objects.filter(pk=branch.pk).exists()

    def test_schedule_for_deletion_with_default_grace_period(self, client, platform_admin, tenant):
        """Test scheduling tenant for deletion with default grace period (30 days)."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.PENDING_DELETION, "grace_period_days": "30"})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.PENDING_DELETION
            assert tenant.scheduled_deletion_at is not None
            assert tenant.deletion_grace_period_days == 30

            # Verify deletion date is approximately 30 days from now
            expected_date = timezone.now() + timedelta(days=30)
            delta = abs((tenant.scheduled_deletion_at - expected_date).total_seconds())
            assert delta < 60  # Within 1 minute

    def test_schedule_for_deletion_with_custom_grace_period(self, client, platform_admin, tenant):
        """Test scheduling tenant for deletion with custom grace period."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.PENDING_DELETION, "grace_period_days": "60"})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.PENDING_DELETION
            assert tenant.deletion_grace_period_days == 60

            # Verify deletion date is approximately 60 days from now
            expected_date = timezone.now() + timedelta(days=60)
            delta = abs((tenant.scheduled_deletion_at - expected_date).total_seconds())
            assert delta < 60  # Within 1 minute

    def test_schedule_for_deletion_rejects_invalid_grace_period(
        self, client, platform_admin, tenant
    ):
        """Test that invalid grace periods are rejected."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})

        # Test grace period too short
        response = client.post(url, {"status": Tenant.PENDING_DELETION, "grace_period_days": "0"})

        # Should redirect with error
        assert response.status_code == 302

        # Status should not change
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE

        # Test grace period too long
        response = client.post(url, {"status": Tenant.PENDING_DELETION, "grace_period_days": "400"})

        assert response.status_code == 302
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE

    def test_reactivate_suspended_tenant(self, client, platform_admin):
        """Test reactivating a suspended tenant."""
        with bypass_rls():
            tenant = create_tenant(
                company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
            )
            tenant.suspended_at = timezone.now()
            tenant.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.ACTIVE})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE
            assert tenant.suspended_at is None

    def test_reactivate_pending_deletion_tenant(self, client, platform_admin):
        """Test reactivating a tenant pending deletion (cancel deletion)."""
        with bypass_rls():
            tenant = create_tenant(
                company_name="Pending Shop", slug="pending-shop", status=Tenant.PENDING_DELETION
            )
            tenant.scheduled_deletion_at = timezone.now() + timedelta(days=30)
            tenant.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(url, {"status": Tenant.ACTIVE})

        assert response.status_code == 302

        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE
            assert tenant.scheduled_deletion_at is None
            assert tenant.suspended_at is None

    def test_days_until_deletion_calculation(self, tenant):
        """Test calculation of days until deletion."""
        # Schedule for deletion 10 days from now
        with bypass_rls():
            tenant.scheduled_deletion_at = timezone.now() + timedelta(days=10)
            tenant.save()

            days = tenant.days_until_deletion()
            # Allow for timing differences (9 or 10 days is acceptable)
            assert days in [9, 10]

    def test_days_until_deletion_returns_none_when_not_scheduled(self, tenant):
        """Test that days_until_deletion returns None when not scheduled."""
        assert tenant.scheduled_deletion_at is None
        assert tenant.days_until_deletion() is None

    def test_days_until_deletion_returns_zero_when_past_due(self, tenant):
        """Test that days_until_deletion returns 0 when past deletion date."""
        # Schedule for deletion in the past
        with bypass_rls():
            tenant.scheduled_deletion_at = timezone.now() - timedelta(days=5)
            tenant.save()

            days = tenant.days_until_deletion()
            assert days == 0

    def test_tenant_model_suspend_method(self, tenant):
        """Test the Tenant.suspend() method."""
        with bypass_rls():
            assert tenant.status == Tenant.ACTIVE
            assert tenant.suspended_at is None

            tenant.suspend(reason="Test suspension")

            assert tenant.status == Tenant.SUSPENDED
            assert tenant.suspended_at is not None

    def test_tenant_model_activate_method(self, tenant):
        """Test the Tenant.activate() method."""
        with bypass_rls():
            tenant.status = Tenant.SUSPENDED
            tenant.suspended_at = timezone.now()
            tenant.save()

            tenant.activate()

            assert tenant.status == Tenant.ACTIVE
            assert tenant.suspended_at is None

    def test_tenant_model_schedule_for_deletion_method(self, tenant):
        """Test the Tenant.schedule_for_deletion() method."""
        with bypass_rls():
            tenant.schedule_for_deletion(grace_period_days=45)

            assert tenant.status == Tenant.PENDING_DELETION
            assert tenant.scheduled_deletion_at is not None
            assert tenant.deletion_grace_period_days == 45

    def test_tenant_model_cancel_deletion_method(self, tenant):
        """Test the Tenant.cancel_deletion() method."""
        with bypass_rls():
            tenant.schedule_for_deletion(grace_period_days=30)
            assert tenant.status == Tenant.PENDING_DELETION

            tenant.cancel_deletion()

            assert tenant.status == Tenant.ACTIVE
            assert tenant.scheduled_deletion_at is None

    def test_tenant_model_is_suspended_method(self, tenant):
        """Test the Tenant.is_suspended() method."""
        with bypass_rls():
            assert not tenant.is_suspended()

            tenant.status = Tenant.SUSPENDED
            tenant.save()

            assert tenant.is_suspended()

    def test_tenant_model_is_pending_deletion_method(self, tenant):
        """Test the Tenant.is_pending_deletion() method."""
        with bypass_rls():
            assert not tenant.is_pending_deletion()

            tenant.status = Tenant.PENDING_DELETION
            tenant.save()

            assert tenant.is_pending_deletion()

    def test_status_change_with_reason_logged(self, client, platform_admin, tenant, caplog):
        """Test that status changes with reasons are logged."""
        import logging

        caplog.set_level(logging.INFO)

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})
        response = client.post(
            url, {"status": Tenant.SUSPENDED, "reason": "Payment overdue for 60 days"}
        )

        assert response.status_code == 302

        # Check that the reason was logged
        assert "Payment overdue for 60 days" in caplog.text

    def test_tenant_detail_shows_suspended_at_timestamp(self, client, platform_admin):
        """Test that tenant detail page shows suspended_at timestamp."""
        with bypass_rls():
            tenant = create_tenant(
                company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
            )
            tenant.suspended_at = timezone.now()
            tenant.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Suspended At" in content

    def test_tenant_detail_shows_deletion_countdown(self, client, platform_admin):
        """Test that tenant detail page shows deletion countdown."""
        with bypass_rls():
            tenant = create_tenant(
                company_name="Pending Shop", slug="pending-shop", status=Tenant.PENDING_DELETION
            )
            tenant.scheduled_deletion_at = timezone.now() + timedelta(days=15)
            tenant.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Scheduled Deletion" in content
        # Allow for timing differences (14 or 15 days is acceptable)
        assert ("15 days remaining" in content or "14 days remaining" in content)

    def test_tenant_detail_shows_warning_banner_for_suspended(self, client, platform_admin):
        """Test that tenant detail shows warning banner for suspended tenants."""
        tenant = create_tenant(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Tenant Suspended" in content

    def test_tenant_detail_shows_warning_banner_for_pending_deletion(self, client, platform_admin):
        """Test that tenant detail shows warning banner for pending deletion."""
        with bypass_rls():
            tenant = create_tenant(
                company_name="Pending Shop", slug="pending-shop", status=Tenant.PENDING_DELETION
            )
            tenant.scheduled_deletion_at = timezone.now() + timedelta(days=20)
            tenant.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Tenant Scheduled for Deletion" in content
        assert "Warning" in content

    def test_complete_status_lifecycle(self, client, platform_admin, tenant):
        """Test complete status lifecycle: active -> suspended -> pending deletion -> active."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_status_change", kwargs={"pk": tenant.pk})

        # 1. Start as active
        with bypass_rls():
            assert tenant.status == Tenant.ACTIVE

        # 2. Suspend
        response = client.post(url, {"status": Tenant.SUSPENDED})
        assert response.status_code == 302
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.SUSPENDED
            assert tenant.suspended_at is not None

        # 3. Schedule for deletion
        response = client.post(url, {"status": Tenant.PENDING_DELETION, "grace_period_days": "30"})
        assert response.status_code == 302
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.PENDING_DELETION
            assert tenant.scheduled_deletion_at is not None

        # 4. Reactivate (cancel deletion)
        response = client.post(url, {"status": Tenant.ACTIVE})
        assert response.status_code == 302
        with bypass_rls():
            tenant.refresh_from_db()
            assert tenant.status == Tenant.ACTIVE
            assert tenant.suspended_at is None
            assert tenant.scheduled_deletion_at is None
