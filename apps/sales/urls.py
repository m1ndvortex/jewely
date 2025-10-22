"""
URL configuration for sales app.
"""

from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    # POS Interface
    path("pos/", views.pos_interface, name="pos_interface"),
    # POS API Endpoints
    path("api/pos/search/products/", views.pos_product_search, name="pos_product_search"),
    path("api/pos/search/customers/", views.pos_customer_search, name="pos_customer_search"),
    path(
        "api/pos/customers/quick-add/", views.pos_customer_quick_add, name="pos_customer_quick_add"
    ),
    path("api/pos/terminals/", views.pos_terminals, name="pos_terminals"),
    path("api/pos/sales/create/", views.pos_create_sale, name="pos_create_sale"),
    path("api/pos/sales/<uuid:sale_id>/hold/", views.pos_hold_sale, name="pos_hold_sale"),
    path("api/pos/sales/held/", views.pos_held_sales, name="pos_held_sales"),
    path(
        "api/pos/validate-inventory/", views.pos_validate_inventory, name="pos_validate_inventory"
    ),
    path("api/pos/calculate-totals/", views.pos_calculate_totals, name="pos_calculate_totals"),
    path(
        "api/pos/offline/sync-validation/",
        views.pos_offline_sync_validation,
        name="pos_offline_sync_validation",
    ),
    path("api/pos/favorite-products/", views.pos_favorite_products, name="pos_favorite_products"),
    path(
        "api/pos/recent-transactions/",
        views.pos_recent_transactions,
        name="pos_recent_transactions",
    ),
    # Sale Management API
    path("api/sales/", views.SaleListView.as_view(), name="sale_list"),
    path("api/sales/<uuid:id>/", views.SaleDetailView.as_view(), name="sale_detail"),
    # Customer Management API
    path("api/customers/", views.CustomerListView.as_view(), name="customer_list"),
    # Receipt Generation
    path("receipts/html/<uuid:sale_id>/", views.receipt_html, name="receipt_html_standard"),
    path(
        "receipts/html/<uuid:sale_id>/<str:format_type>/", views.receipt_html, name="receipt_html"
    ),
    path("receipts/pdf/<uuid:sale_id>/", views.receipt_pdf, name="receipt_pdf_standard"),
    path("receipts/pdf/<uuid:sale_id>/<str:format_type>/", views.receipt_pdf, name="receipt_pdf"),
    path(
        "api/receipts/<uuid:sale_id>/generate/",
        views.generate_receipt_after_sale,
        name="generate_receipt",
    ),
]
