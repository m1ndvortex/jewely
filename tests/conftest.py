"""
Pytest configuration and fixtures for the jewelry shop SaaS platform.
"""

from django.conf import settings

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """
    Configure the test database and verify RLS configuration.

    IMPORTANT: The tenants table MUST have RLS enabled for proper tenant isolation.
    Tenants can only see their own record. Platform admins use RLS bypass to see all.
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
    # This runs after migrations, so we can verify RLS is properly enabled
    with django_db_blocker.unblock():
        from django.db import connection

        with connection.cursor() as cursor:
            # Ensure tenants table HAS RLS enabled with FORCE
            # This is critical for tenant isolation
            cursor.execute(
                """
                ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
                ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
            """
            )

            # Verify it worked
            cursor.execute(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = 'tenants';
            """
            )
            result = cursor.fetchone()
            if result:
                relname, rls_enabled, rls_forced = result
                msg = (
                    f"RLS not properly enabled on {relname}: rls={rls_enabled}, forced={rls_forced}"
                )
                assert rls_enabled and rls_forced, msg


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
