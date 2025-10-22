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
]
