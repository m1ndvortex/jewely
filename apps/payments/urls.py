"""
URL configuration for payments app.

This module defines URL patterns for:
- Subscription dashboard
- Plan listing and selection
- Purchase flow
- Payment processing
- History and management
"""

from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    # Dashboard
    path(
        "subscription/",
        views.SubscriptionDashboardView.as_view(),
        name="subscription_dashboard",
    ),
    # Plans
    path(
        "subscription/plans/",
        views.SubscriptionPlansView.as_view(),
        name="subscription_plans",
    ),
    # Purchase flow
    path(
        "subscription/purchase/",
        views.PurchaseSubscriptionView.as_view(),
        name="purchase_subscription",
    ),
    # Payment processing
    path(
        "subscription/payment/<uuid:purchase_id>/",
        views.PaymentGatewayView.as_view(),
        name="payment_gateway",
    ),
    path(
        "subscription/payment/<uuid:purchase_id>/placeholder/",
        views.ProcessPlaceholderPaymentView.as_view(),
        name="process_placeholder_payment",
    ),
    path(
        "subscription/payment/callback/<str:gateway>/",
        views.PaymentCallbackView.as_view(),
        name="payment_callback",
    ),
    # History
    path(
        "subscription/history/",
        views.PurchaseHistoryView.as_view(),
        name="purchase_history",
    ),
    path(
        "subscription/purchase/<uuid:pk>/",
        views.PurchaseDetailView.as_view(),
        name="purchase_detail",
    ),
    # Subscription management
    path(
        "subscription/renew/",
        views.SubscriptionRenewalView.as_view(),
        name="subscription_renewal",
    ),
    path(
        "subscription/upgrade/",
        views.SubscriptionUpgradeView.as_view(),
        name="subscription_upgrade",
    ),
    path(
        "subscription/cancel/",
        views.SubscriptionCancellationView.as_view(),
        name="subscription_cancellation",
    ),
    # API endpoints
    path(
        "api/calculate-pricing/",
        views.CalculatePricingAPIView.as_view(),
        name="calculate_pricing_api",
    ),
]
