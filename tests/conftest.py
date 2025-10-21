"""
Pytest configuration and fixtures for the jewelry shop SaaS platform.
"""

from django.conf import settings

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """
    Configure the test database and verify RLS configuration.

    IMPORTANT: The tenants table should NOT have RLS enabled because it's not
    tenant-scoped data. It's the master list of all tenants that platform admins
    need to access. Only tenant-scoped tables (branches, users, etc.) should have RLS.
    """
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_jewelry_shop",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",  # Docker service name
        "PORT": "5432",
        "ATOMIC_REQUESTS": True,
    }

    # After database is created, ensure correct RLS configuration
    # This runs after migrations, so we can fix any issues here
    with django_db_blocker.unblock():
        from django.db import connection

        with connection.cursor() as cursor:
            # Ensure tenants table does NOT have RLS (it's not tenant-scoped)
            # The tenants table is the master list - platform admins need full access
            cursor.execute(
                """
                ALTER TABLE IF EXISTS tenants NO FORCE ROW LEVEL SECURITY;
                ALTER TABLE IF EXISTS tenants DISABLE ROW LEVEL SECURITY;
            """
            )

            # Verify it worked
            cursor.execute(
                """
                SELECT relname, relrowsecurity
                FROM pg_class
                WHERE relname = 'tenants';
            """
            )
            result = cursor.fetchone()
            if result:
                relname, rls_enabled = result
                msg = f"Failed to disable RLS on {relname}"
                assert not rls_enabled, msg


@pytest.fixture
def api_client():
    """
    Fixture for Django REST framework API client.
    """
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authenticated_client(api_client, django_user_model):
    """
    Fixture for authenticated API client.
    """
    user = django_user_model.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )
    api_client.force_authenticate(user=user)
    return api_client, user
