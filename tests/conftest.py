"""
Pytest configuration and fixtures for the jewelry shop SaaS platform.
"""

from django.conf import settings

import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """
    Configure the test database and ensure RLS is enabled.
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

    # After database is created, ensure RLS is enabled on all tables
    with django_db_blocker.unblock():
        from django.db import connection

        with connection.cursor() as cursor:
            # Enable RLS on tenants table (critical for security)
            cursor.execute(
                """
                ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
                ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
            """
            )

            # Verify RLS is enabled
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
                msg = f"RLS not properly enabled on {relname}"
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
