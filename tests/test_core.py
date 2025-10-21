"""
Tests for core functionality.
"""

from django.test import Client
from django.urls import reverse

import pytest


@pytest.mark.django_db
class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check endpoint returns 200 OK."""
        client = Client()
        response = client.get(reverse("core:health_check"))
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_returns_correct_service_name(self):
        """Test that health check returns correct service name."""
        client = Client()
        response = client.get(reverse("core:health_check"))
        data = response.json()
        assert "service" in data
        assert data["service"] == "jewelry-shop-saas"


@pytest.mark.django_db
class TestHomeView:
    """Test home view."""

    def test_home_returns_200(self):
        """Test that home endpoint returns 200 OK."""
        client = Client()
        response = client.get(reverse("core:home"))
        assert response.status_code == 200

    def test_home_returns_welcome_message(self):
        """Test that home returns welcome message."""
        client = Client()
        response = client.get(reverse("core:home"))
        data = response.json()
        assert "message" in data
        assert "Jewelry Shop SaaS Platform" in data["message"]

    def test_home_returns_version(self):
        """Test that home returns version information."""
        client = Client()
        response = client.get(reverse("core:home"))
        data = response.json()
        assert "version" in data
