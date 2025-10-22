"""
URL configuration for CRM app.

Implements Requirement 12: Customer Relationship Management (CRM)
"""

from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    # Customer management views
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/create/", views.customer_create, name="customer_create"),
    path("customers/<uuid:customer_id>/", views.customer_detail, name="customer_detail"),
    path("customers/<uuid:customer_id>/edit/", views.customer_edit, name="customer_edit"),
    path(
        "customers/<uuid:customer_id>/communication/add/",
        views.customer_communication_add,
        name="customer_communication_add",
    ),
    # Loyalty program views
    path("loyalty/tiers/", views.loyalty_tier_list, name="loyalty_tier_list"),
    path("loyalty/tiers/create/", views.loyalty_tier_create, name="loyalty_tier_create"),
    path("loyalty/tiers/<uuid:tier_id>/edit/", views.loyalty_tier_edit, name="loyalty_tier_edit"),
    path(
        "customers/<uuid:customer_id>/loyalty/redeem/",
        views.loyalty_points_redeem,
        name="loyalty_points_redeem",
    ),
    path(
        "customers/<uuid:customer_id>/loyalty/adjust/",
        views.loyalty_points_adjust,
        name="loyalty_points_adjust",
    ),
    path(
        "customers/<uuid:customer_id>/loyalty/upgrade-check/",
        views.loyalty_tier_upgrade_check,
        name="loyalty_tier_upgrade_check",
    ),
    path(
        "customers/<uuid:customer_id>/loyalty/transfer/",
        views.loyalty_points_transfer,
        name="loyalty_points_transfer",
    ),
    path(
        "customers/<uuid:customer_id>/loyalty/expire/",
        views.loyalty_points_expire,
        name="loyalty_points_expire",
    ),
    path("referrals/stats/", views.referral_stats, name="referral_stats"),
    # API endpoints
    path("api/customers/", views.CustomerListAPIView.as_view(), name="api_customer_list"),
    path(
        "api/customers/<uuid:pk>/",
        views.CustomerDetailAPIView.as_view(),
        name="api_customer_detail",
    ),
    path(
        "api/customers/create/",
        views.CustomerCreateAPIView.as_view(),
        name="api_customer_create",
    ),
    path(
        "api/customers/<uuid:pk>/update/",
        views.CustomerUpdateAPIView.as_view(),
        name="api_customer_update",
    ),
]
