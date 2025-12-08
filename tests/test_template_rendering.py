"""
Test template rendering for advanced tenant management.
"""

from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import timezone

import pytest

from apps.core.models import Branch, Tenant, TenantDomain, TenantSettings, User


@pytest.mark.django_db
class TestTemplateRendering:
    """Test that all tenant management templates render without errors."""

    def test_tenant_form_template_renders(self):
        """Test tenant_form.html renders correctly."""
        context = {
            "form": None,  # Form would be provided by view
            "is_create": True,
        }
        html = render_to_string("admin/tenant_form.html", context)
        assert html is not None
        assert len(html) > 0

    def test_password_modal_template_renders(self):
        """Test password_modal.html renders correctly."""
        context = {
            "password": "TestPassword123!",
            "username": "testuser",
        }
        html = render_to_string("admin/partials/password_modal.html", context)
        assert html is not None
        assert "TestPassword123!" in html
        assert "testuser" in html

    def test_tenant_list_template_renders(self, tenant):
        """Test tenant_list.html renders correctly."""
        context = {
            "tenants": [tenant],
            "page_obj": None,
        }
        html = render_to_string("admin/tenant_list.html", context)
        assert html is not None
        assert len(html) > 0

    def test_bulk_action_modal_template_renders(self):
        """Test bulk_action_modal.html renders correctly."""
        context = {
            "action": "activate",
            "count": 5,
        }
        html = render_to_string("admin/partials/bulk_action_modal.html", context)
        assert html is not None
        assert "5" in html

    def test_tenant_detail_template_renders(self, tenant):
        """Test tenant_detail.html renders correctly."""
        factory = RequestFactory()
        request = factory.get("/admin/tenants/1/")

        context = {
            "tenant": tenant,
            "active_tab": "info",
            "request": request,
        }
        html = render_to_string("admin/tenant_detail.html", context)
        assert html is not None
        assert tenant.company_name in html

    def test_tenant_info_tab_renders(self, tenant):
        """Test tenant_info_tab.html renders correctly."""
        context = {
            "tenant": tenant,
            "statistics": {
                "user_count": 5,
                "active_users": 4,
                "inactive_users": 1,
                "users_by_role": {},
            },
            "owner": None,
            "domains": [],
            "settings": tenant.settings,
        }
        html = render_to_string("admin/partials/tenant_info_tab.html", context)
        assert html is not None
        assert "5" in html  # user count

    def test_tenant_users_tab_renders(self, tenant, user):
        """Test tenant_users_tab.html renders correctly."""
        context = {
            "tenant": tenant,
            "users": [user],
            "user_count": 1,
            "search_query": "",
            "role_filter": "",
            "status_filter": "",
            "role_choices": User.ROLE_CHOICES,
            "branches": [],
        }
        html = render_to_string("admin/partials/tenant_users_tab.html", context)
        assert html is not None
        assert user.username in html

    def test_tenant_users_modals_renders(self, tenant):
        """Test tenant_users_modals.html renders correctly."""
        context = {
            "tenant": tenant,
            "role_choices": User.ROLE_CHOICES,
            "branches": [],
        }
        html = render_to_string("admin/partials/tenant_users_modals.html", context)
        assert html is not None
        assert len(html) > 0

    def test_user_edit_modal_renders(self, user):
        """Test user_edit_modal.html renders correctly."""
        context = {
            "user": user,
            "login_history": [],
            "failed_logins_24h": 0,
            "role_choices": User.ROLE_CHOICES,
            "branches": [],
        }
        html = render_to_string("admin/partials/user_edit_modal.html", context)
        assert html is not None
        assert user.username in html

    def test_tenant_settings_tab_renders(self, tenant):
        """Test tenant_settings_tab.html renders correctly."""
        context = {
            "tenant": tenant,
            "settings": tenant.settings,
            "timezone_choices": ["UTC", "America/New_York"],
            "currency_choices": TenantSettings.CURRENCY_CHOICES,
            "date_format_choices": TenantSettings.DATE_FORMAT_CHOICES,
        }
        html = render_to_string("admin/partials/tenant_settings_tab.html", context)
        assert html is not None
        assert len(html) > 0

    def test_tenant_activity_tab_renders(self, tenant):
        """Test tenant_activity_tab.html renders correctly."""
        context = {
            "tenant": tenant,
            "audit_logs": [],
            "date_range": "7d",
            "category_filter": "",
            "actor_filter": "",
            "category_choices": [],
            "tenant_users": [],
        }
        html = render_to_string("admin/partials/tenant_activity_tab.html", context)
        assert html is not None
        assert len(html) > 0

    def test_activity_detail_modal_renders(self):
        """Test activity_detail_modal.html renders correctly."""
        context = {
            "log": {
                "action": "USER_CREATE",
                "description": "Created user",
                "old_values": {},
                "new_values": {"username": "newuser"},
                "metadata": {},
            }
        }
        html = render_to_string("admin/partials/activity_detail_modal.html", context)
        assert html is not None
        assert "USER_CREATE" in html
