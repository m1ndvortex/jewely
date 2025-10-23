"""
URL configuration for inventory app.
"""

from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    # Inventory Item endpoints
    path("api/inventory/items/", views.InventoryItemListView.as_view(), name="item_list"),
    path(
        "api/inventory/items/create/", views.InventoryItemCreateView.as_view(), name="item_create"
    ),
    path(
        "api/inventory/items/<uuid:id>/",
        views.InventoryItemDetailView.as_view(),
        name="item_detail",
    ),
    path(
        "api/inventory/items/<uuid:id>/update/",
        views.InventoryItemUpdateView.as_view(),
        name="item_update",
    ),
    path(
        "api/inventory/items/<uuid:id>/delete/",
        views.InventoryItemDeleteView.as_view(),
        name="item_delete",
    ),
    path(
        "api/inventory/items/<uuid:item_id>/adjust-stock/",
        views.stock_adjustment,
        name="stock_adjustment",
    ),
    # Product Category endpoints
    path(
        "api/inventory/categories/", views.ProductCategoryListView.as_view(), name="category_list"
    ),
    path(
        "api/inventory/categories/create/",
        views.ProductCategoryCreateView.as_view(),
        name="category_create",
    ),
    path(
        "api/inventory/categories/<uuid:id>/",
        views.ProductCategoryDetailView.as_view(),
        name="category_detail",
    ),
    path(
        "api/inventory/categories/<uuid:id>/update/",
        views.ProductCategoryUpdateView.as_view(),
        name="category_update",
    ),
    path(
        "api/inventory/categories/<uuid:id>/delete/",
        views.ProductCategoryDeleteView.as_view(),
        name="category_delete",
    ),
    # Barcode scanning and lookup
    path(
        "api/inventory/lookup-by-barcode/",
        views.lookup_by_barcode,
        name="lookup_by_barcode",
    ),
    # Barcode and QR Code generation endpoints
    path(
        "api/inventory/items/<uuid:item_id>/barcode/",
        views.generate_barcode,
        name="generate_barcode",
    ),
    path(
        "api/inventory/items/<uuid:item_id>/qrcode/",
        views.generate_qr_code,
        name="generate_qr_code",
    ),
    path(
        "api/inventory/items/<uuid:item_id>/label/",
        views.generate_product_label,
        name="generate_product_label",
    ),
    path(
        "api/inventory/items/<uuid:item_id>/qr-label/",
        views.generate_qr_label,
        name="generate_qr_label",
    ),
    # Inventory Reports
    path(
        "api/inventory/reports/valuation/",
        views.inventory_valuation_report,
        name="report_valuation",
    ),
    path(
        "api/inventory/reports/low-stock/",
        views.low_stock_alert_report,
        name="report_low_stock",
    ),
    path(
        "api/inventory/reports/dead-stock/",
        views.dead_stock_analysis_report,
        name="report_dead_stock",
    ),
    path(
        "api/inventory/reports/turnover/",
        views.inventory_turnover_report,
        name="report_turnover",
    ),
    # Inventory Transfer endpoints
    path(
        "api/inventory/transfers/",
        views.InventoryTransferListView.as_view(),
        name="transfer_list",
    ),
    path(
        "api/inventory/transfers/create/",
        views.InventoryTransferCreateView.as_view(),
        name="transfer_create",
    ),
    path(
        "api/inventory/transfers/<uuid:id>/",
        views.InventoryTransferDetailView.as_view(),
        name="transfer_detail",
    ),
    path(
        "api/inventory/transfers/<uuid:transfer_id>/approve/",
        views.approve_transfer,
        name="transfer_approve",
    ),
    path(
        "api/inventory/transfers/<uuid:transfer_id>/reject/",
        views.reject_transfer,
        name="transfer_reject",
    ),
    path(
        "api/inventory/transfers/<uuid:transfer_id>/ship/",
        views.ship_transfer,
        name="transfer_ship",
    ),
    path(
        "api/inventory/transfers/<uuid:transfer_id>/receive/",
        views.receive_transfer,
        name="transfer_receive",
    ),
    path(
        "api/inventory/transfers/<uuid:transfer_id>/cancel/",
        views.cancel_transfer,
        name="transfer_cancel",
    ),
]
