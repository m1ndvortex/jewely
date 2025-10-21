"""
Pytest configuration and fixtures for the jewelry shop SaaS platform.
"""

from django.conf import settings

import pytest


@pytest.fixture(scope="session")
def django_db_setup():
    """
    Configure the test database.
    """
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_jewelry_shop",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
        "ATOMIC_REQUESTS": True,
    }


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
