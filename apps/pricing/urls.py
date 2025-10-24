"""
URL patterns for pricing app.
"""

from django.urls import path

from apps.pricing import views

app_name = "pricing"

urlpatterns = [
    # Dashboard
    path("", views.pricing_dashboard, name="dashboard"),
    # Price calculation
    path("calculate/", views.calculate_price, name="calculate_price"),
    path(
        "api/calculate/<uuid:item_id>/",
        views.api_calculate_item_price,
        name="api_calculate_item_price",
    ),
    # Gold rate displays
    path("gold-rates/widget/", views.gold_rate_widget, name="gold_rate_widget"),
    path("gold-rates/history/", views.gold_rate_history, name="gold_rate_history"),
    path("gold-rates/comparison/", views.gold_rate_comparison, name="gold_rate_comparison"),
    path("api/gold-rates/", views.api_gold_rates, name="api_gold_rates"),
    # Price recalculation
    path("recalculate/all/", views.recalculate_all_prices, name="recalculate_all"),
    path("recalculate/karat/", views.recalculate_by_karat, name="recalculate_by_karat"),
    # Price overrides
    path("overrides/", views.price_override_list, name="override_list"),
    path("overrides/<uuid:override_id>/", views.price_override_detail, name="override_detail"),
    path("overrides/request/", views.request_price_override, name="request_override"),
    path(
        "overrides/<uuid:override_id>/approve/",
        views.approve_price_override,
        name="approve_override",
    ),
    path(
        "overrides/<uuid:override_id>/reject/", views.reject_price_override, name="reject_override"
    ),
    # Price change history
    path("history/", views.price_change_history, name="change_history"),
]
