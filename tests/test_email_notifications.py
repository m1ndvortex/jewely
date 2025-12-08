"""
Tests for email notification functionality.

Tests the welcome email and password reset email features.
Requirements: 1.10, 3.10
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

import pytest

from apps.core.models import Tenant, TenantDomain, TenantSettings
from apps.core.services.tenant_service import TenantService
from apps.core.services.user_service import UserManagementService

User = get_user_model()


@pytest.mark.django_db
class TestWelcomeEmail(TestCase):
    """Test welcome email functionality."""

    def setUp(self):
        """Set up test data."""
        # Create a platform admin user
        self.admin = User.objects.create_user(
            username="admin_welcome",
            email="admin_welcome@test.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
        )

    def test_send_welcome_email_success(self):
        """Test that welcome email is sent successfully."""
        # Clear the mail outbox
        mail.outbox = []

        # Create tenant with owner
        tenant_service = TenantService()
        tenant, owner, password = tenant_service.create_tenant_with_owner(
            tenant_data={
                "company_name": "Test Jewelry Shop",
                "slug": "test-shop",
                "status": Tenant.ACTIVE,
            },
            settings_data={
                "email": "business@testshop.com",
                "timezone": "UTC",
            },
            owner_data={
                "username": "testowner",
                "email": "owner@testshop.com",
            },
            domain_data={},
            created_by=self.admin,
        )

        # Send welcome email
        result = tenant_service.send_welcome_email(
            tenant=tenant,
            owner=owner,
            initial_password=password,
        )

        # Verify email was sent
        assert result is True
        assert len(mail.outbox) == 1

        # Check email content
        email = mail.outbox[0]
        assert email.subject == f"Welcome to Jewelry Management System - {tenant.company_name}"
        assert owner.email in email.to
        assert password in email.body
        assert tenant.company_name in email.body

    def test_welcome_email_contains_required_info(self):
        """Test that welcome email contains all required information."""
        mail.outbox = []

        tenant_service = TenantService()
        tenant, owner, password = tenant_service.create_tenant_with_owner(
            tenant_data={
                "company_name": "Test Shop 2",
                "slug": "test-shop-2",
            },
            settings_data={"email": "test@test.com"},
            owner_data={
                "username": "owner2",
                "email": "owner2@test.com",
            },
            domain_data={},
            created_by=self.admin,
        )

        tenant_service.send_welcome_email(
            tenant=tenant,
            owner=owner,
            initial_password=password,
        )

        email = mail.outbox[0]

        # Check required information is present
        assert owner.username in email.body
        assert owner.email in email.body
        assert password in email.body
        assert "login" in email.body.lower()


@pytest.mark.django_db
class TestPasswordResetEmail(TestCase):
    """Test password reset email functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Tenant",
            slug="test-tenant-reset",
        )
        TenantSettings.objects.create(tenant=self.tenant)
        TenantDomain.objects.create(
            tenant=self.tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            domain="test-tenant-reset.local",
            is_primary=True,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,
        )

        # Create admin user
        self.admin = User.objects.create_user(
            username="admin_reset",
            email="admin_reset@test.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant user
        self.user = User.objects.create_user(
            username="testuser",
            email="user@test.com",
            password="password123",
            tenant=self.tenant,
            role=User.TENANT_EMPLOYEE,
        )

    def test_send_password_reset_email_success(self):
        """Test that password reset email is sent successfully."""
        mail.outbox = []

        user_service = UserManagementService()
        result = user_service.send_password_reset_email(
            user=self.user,
            sent_by=self.admin,
        )

        # Verify email was sent
        assert result is True
        assert len(mail.outbox) == 1

        # Check email content
        email = mail.outbox[0]
        assert "Password Reset" in email.subject
        assert self.user.email in email.to
        assert "reset" in email.body.lower()

    def test_password_reset_email_contains_link(self):
        """Test that password reset email contains reset link."""
        mail.outbox = []

        user_service = UserManagementService()
        user_service.send_password_reset_email(
            user=self.user,
            sent_by=self.admin,
        )

        email = mail.outbox[0]

        # Check that email contains a URL
        assert "http" in email.body
        assert "reset" in email.body.lower()
