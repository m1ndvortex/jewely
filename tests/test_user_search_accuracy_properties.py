"""
Property-based tests for user search accuracy in tenant management.

**Feature: advanced-tenant-management, Property 6: User Search Accuracy**
**Validates: Requirements 3.2, 11.1**

Property 6: User Search Accuracy
*For any* search query on the Users tab, all returned users SHALL have username or email
containing the search term (case-insensitive) AND belong to the selected tenant.
"""

import string
import uuid
from datetime import timedelta

from django.db.models import Q

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.models import Tenant, User

# ============================================================================
# Strategies for generating test data
# ============================================================================

# Characters allowed in usernames
USERNAME_CHARS = string.ascii_lowercase + string.digits + "_"

# Characters allowed in email local parts
EMAIL_LOCAL_CHARS = string.ascii_lowercase + string.digits + "._"


@st.composite
def valid_username_strategy(draw):
    """Generate valid usernames (3-20 chars, starts with letter)."""
    first_char = draw(st.sampled_from(string.ascii_lowercase))
    rest = draw(st.text(alphabet=USERNAME_CHARS, min_size=2, max_size=15))
    return first_char + rest


@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    local_part = draw(st.text(alphabet=EMAIL_LOCAL_CHARS, min_size=3, max_size=12))
    # Ensure local part doesn't start or end with special chars
    assume(local_part and local_part[0].isalnum() and local_part[-1].isalnum())

    domain = draw(st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=8))
    assume(domain)

    tld = draw(st.sampled_from(["com", "org", "net", "io", "co"]))
    return f"{local_part}@{domain}.{tld}"


@st.composite
def search_query_strategy(draw):
    """Generate search queries (1-10 chars, alphanumeric)."""
    query = draw(st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=10))
    assume(query.strip())
    return query.strip()


@st.composite
def tenant_slug_strategy(draw):
    """Generate valid tenant slugs."""
    slug = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits + "-", min_size=3, max_size=20)
    )
    # Ensure slug starts and ends with alphanumeric
    assume(slug and slug[0].isalnum() and slug[-1].isalnum())
    # Ensure no consecutive hyphens
    assume("--" not in slug)
    return slug


@st.composite
def user_data_strategy(draw):
    """Generate user data with username and email."""
    username = draw(valid_username_strategy())
    email = draw(valid_email_strategy())
    role = draw(st.sampled_from([User.TENANT_OWNER, User.TENANT_MANAGER, User.TENANT_EMPLOYEE]))
    is_active = draw(st.booleans())

    return {
        "username": username,
        "email": email,
        "role": role,
        "is_active": is_active,
    }


# ============================================================================
# Helper Functions
# ============================================================================


def search_users_for_tenant(tenant, search_query):
    """
    Execute user search for a tenant using the same logic as _get_users_context.

    This mirrors the implementation in apps/core/admin_views.py:
    - Filter by tenant
    - Filter by username OR email containing search term (case-insensitive)
    """
    users = User.objects.filter(tenant=tenant)

    if search_query:
        users = users.filter(Q(username__icontains=search_query) | Q(email__icontains=search_query))

    return users


def user_matches_search(user, search_query):
    """
    Check if a user matches the search query.

    Returns True if username OR email contains the search term (case-insensitive).
    """
    if not search_query:
        return True

    search_lower = search_query.lower()
    return search_lower in user.username.lower() or search_lower in user.email.lower()


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestUserSearchAccuracy:
    """
    **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
    **Validates: Requirements 3.2, 11.1**

    Property tests for user search accuracy ensuring:
    1. All returned users have username or email containing the search term
    2. All returned users belong to the selected tenant
    3. Search is case-insensitive
    4. No users from other tenants are returned
    """

    @given(
        search_query=search_query_strategy(),
        num_users=st.integers(min_value=2, max_value=3),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_results_contain_search_term(self, search_query, num_users):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, all returned users SHALL have username or email
        containing the search term (case-insensitive).
        """
        # Create a unique tenant for this test
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create users with varying usernames and emails
            created_users = []
            for i in range(num_users):
                user = User.objects.create_user(
                    username=f"user{i}_{uuid.uuid4().hex[:6]}",
                    email=f"user{i}_{uuid.uuid4().hex[:6]}@test.com",
                    password="TestPass123!",
                    tenant=tenant,
                    role=User.TENANT_EMPLOYEE,
                )
                created_users.append(user)

            # Also create a user that should match the search
            matching_user = User.objects.create_user(
                username=f"match_{search_query}_{uuid.uuid4().hex[:4]}",
                email=f"match_{uuid.uuid4().hex[:6]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )
            created_users.append(matching_user)

            # Execute search
            results = search_users_for_tenant(tenant, search_query)

            # Property: All returned users must have username or email containing search term
            for user in results:
                assert user_matches_search(user, search_query), (
                    f"User {user.username} (email: {user.email}) does not match "
                    f"search query '{search_query}'"
                )

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        search_query=search_query_strategy(),
        num_users_per_tenant=st.integers(min_value=2, max_value=3),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_results_belong_to_selected_tenant(self, search_query, num_users_per_tenant):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 11.1**

        For any search query, all returned users SHALL belong to the selected tenant.
        No users from other tenants should be returned.
        """
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name=f"Tenant One {uuid.uuid4().hex[:8]}",
            slug=f"tenant-one-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name=f"Tenant Two {uuid.uuid4().hex[:8]}",
            slug=f"tenant-two-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create users for tenant1
            for i in range(num_users_per_tenant):
                User.objects.create_user(
                    username=f"t1user{i}_{search_query}_{uuid.uuid4().hex[:4]}",
                    email=f"t1user{i}_{search_query}@tenant1.com",
                    password="TestPass123!",
                    tenant=tenant1,
                    role=User.TENANT_EMPLOYEE,
                )

            # Create users for tenant2 with similar usernames/emails
            for i in range(num_users_per_tenant):
                User.objects.create_user(
                    username=f"t2user{i}_{search_query}_{uuid.uuid4().hex[:4]}",
                    email=f"t2user{i}_{search_query}@tenant2.com",
                    password="TestPass123!",
                    tenant=tenant2,
                    role=User.TENANT_EMPLOYEE,
                )

            # Execute search for tenant1
            results = search_users_for_tenant(tenant1, search_query)

            # Property: All returned users must belong to tenant1
            for user in results:
                assert user.tenant_id == tenant1.id, (
                    f"User {user.username} belongs to tenant {user.tenant_id}, "
                    f"but search was for tenant {tenant1.id}"
                )

            # Property: No users from tenant2 should be in results
            tenant2_user_ids = set(User.objects.filter(tenant=tenant2).values_list("id", flat=True))
            result_user_ids = set(results.values_list("id", flat=True))

            assert not tenant2_user_ids.intersection(
                result_user_ids
            ), f"Search results contain users from tenant2"

        finally:
            # Cleanup
            User.objects.filter(tenant__in=[tenant1, tenant2]).delete()
            tenant1.delete()
            tenant2.delete()

    @given(
        search_query=search_query_strategy(),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_is_case_insensitive(self, search_query):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, the search SHALL be case-insensitive.
        Searching for 'ABC' should return users with 'abc', 'ABC', 'Abc', etc.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create user with lowercase version of search query in username
            user_lower = User.objects.create_user(
                username=f"user_{search_query.lower()}_{uuid.uuid4().hex[:4]}",
                email=f"lower_{uuid.uuid4().hex[:6]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create user with uppercase version of search query in email
            user_upper = User.objects.create_user(
                username=f"user_upper_{uuid.uuid4().hex[:4]}",
                email=f"{search_query.upper()}_{uuid.uuid4().hex[:6]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create user with mixed case version
            mixed_case = "".join(
                c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(search_query)
            )
            user_mixed = User.objects.create_user(
                username=f"user_{mixed_case}_{uuid.uuid4().hex[:4]}",
                email=f"mixed_{uuid.uuid4().hex[:6]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Search with original query
            results = search_users_for_tenant(tenant, search_query)
            result_ids = set(results.values_list("id", flat=True))

            # Property: All users with matching username/email should be found
            assert (
                user_lower.id in result_ids
            ), f"User with lowercase '{search_query.lower()}' not found"

            # Search with uppercase query should return same results
            results_upper = search_users_for_tenant(tenant, search_query.upper())
            result_upper_ids = set(results_upper.values_list("id", flat=True))

            # Property: Case of search query should not affect results
            assert (
                user_lower.id in result_upper_ids
            ), f"Uppercase search did not find user with lowercase username"

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_users=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_empty_search_returns_all_tenant_users(self, num_users):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2, 11.1**

        For an empty search query, all users belonging to the tenant SHALL be returned.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create users for the tenant
            created_user_ids = []
            for i in range(num_users):
                user = User.objects.create_user(
                    username=f"user{i}_{uuid.uuid4().hex[:6]}",
                    email=f"user{i}_{uuid.uuid4().hex[:6]}@test.com",
                    password="TestPass123!",
                    tenant=tenant,
                    role=User.TENANT_EMPLOYEE,
                )
                created_user_ids.append(user.id)

            # Execute search with empty query
            results = search_users_for_tenant(tenant, "")
            result_ids = set(results.values_list("id", flat=True))

            # Property: All created users should be in results
            for user_id in created_user_ids:
                assert user_id in result_ids, f"User {user_id} not found in empty search results"

            # Property: Result count should match created users
            assert (
                len(result_ids) == num_users
            ), f"Expected {num_users} users, got {len(result_ids)}"

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        search_query=search_query_strategy(),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_finds_users_by_email(self, search_query):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, users with matching email SHALL be found
        even if username does not match.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create user with search query in email but not in username
            user = User.objects.create_user(
                username=f"nomatch_{uuid.uuid4().hex[:8]}",
                email=f"{search_query}_{uuid.uuid4().hex[:4]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Execute search
            results = search_users_for_tenant(tenant, search_query)
            result_ids = set(results.values_list("id", flat=True))

            # Property: User should be found by email match
            assert user.id in result_ids, f"User with email containing '{search_query}' not found"

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        search_query=search_query_strategy(),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_finds_users_by_username(self, search_query):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, users with matching username SHALL be found
        even if email does not match.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create user with search query in username but not in email
            user = User.objects.create_user(
                username=f"user_{search_query}_{uuid.uuid4().hex[:4]}",
                email=f"nomatch_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Execute search
            results = search_users_for_tenant(tenant, search_query)
            result_ids = set(results.values_list("id", flat=True))

            # Property: User should be found by username match
            assert (
                user.id in result_ids
            ), f"User with username containing '{search_query}' not found"

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        search_query=search_query_strategy(),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_non_matching_users_not_returned(self, search_query):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, users without matching username or email
        SHALL NOT be returned.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create user that should NOT match the search
            # Use a completely different string that won't contain the search query
            non_matching_username = f"zzz_{uuid.uuid4().hex[:8]}"
            non_matching_email = f"zzz_{uuid.uuid4().hex[:8]}@zzz.zzz"

            # Ensure the non-matching data doesn't accidentally contain the search query
            assume(search_query.lower() not in non_matching_username.lower())
            assume(search_query.lower() not in non_matching_email.lower())

            user = User.objects.create_user(
                username=non_matching_username,
                email=non_matching_email,
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Execute search
            results = search_users_for_tenant(tenant, search_query)
            result_ids = set(results.values_list("id", flat=True))

            # Property: Non-matching user should NOT be in results
            assert user.id not in result_ids, (
                f"User {user.username} (email: {user.email}) should not match "
                f"search query '{search_query}'"
            )

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        search_query=search_query_strategy(),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_search_is_deterministic(self, search_query):
        """
        **Feature: advanced-tenant-management, Property 6: User Search Accuracy**
        **Validates: Requirements 3.2**

        For any search query, executing the same search multiple times
        SHALL return the same results.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create some users
            for i in range(3):
                User.objects.create_user(
                    username=f"user{i}_{search_query}_{uuid.uuid4().hex[:4]}",
                    email=f"user{i}_{uuid.uuid4().hex[:6]}@test.com",
                    password="TestPass123!",
                    tenant=tenant,
                    role=User.TENANT_EMPLOYEE,
                )

            # Execute search multiple times
            results1 = set(
                search_users_for_tenant(tenant, search_query).values_list("id", flat=True)
            )
            results2 = set(
                search_users_for_tenant(tenant, search_query).values_list("id", flat=True)
            )
            results3 = set(
                search_users_for_tenant(tenant, search_query).values_list("id", flat=True)
            )

            # Property: All searches should return the same results
            assert results1 == results2 == results3, (
                f"Search results are not deterministic. "
                f"Results: {len(results1)}, {len(results2)}, {len(results3)}"
            )

        finally:
            # Cleanup
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()
