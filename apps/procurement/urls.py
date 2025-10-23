"""
URL configuration for procurement app.
"""

from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    # Supplier management URLs
    path("suppliers/", views.SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/create/", views.SupplierCreateView.as_view(), name="supplier_create"),
    path("suppliers/<uuid:pk>/", views.SupplierDetailView.as_view(), name="supplier_detail"),
    path("suppliers/<uuid:pk>/edit/", views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("suppliers/<uuid:pk>/delete/", views.SupplierDeleteView.as_view(), name="supplier_delete"),
    # Supplier rating AJAX
    path("suppliers/<uuid:pk>/rating/", views.update_supplier_rating, name="supplier_rating"),
    # Supplier communications
    path(
        "suppliers/<uuid:pk>/communications/",
        views.supplier_communications,
        name="supplier_communications",
    ),
    path(
        "suppliers/<uuid:supplier_pk>/communications/create/",
        views.SupplierCommunicationCreateView.as_view(),
        name="communication_create",
    ),
    # Supplier documents
    path("suppliers/<uuid:pk>/documents/", views.supplier_documents, name="supplier_documents"),
    path(
        "suppliers/<uuid:supplier_pk>/documents/create/",
        views.SupplierDocumentCreateView.as_view(),
        name="document_create",
    ),
    # Purchase Order URLs
    path("purchase-orders/", views.PurchaseOrderListView.as_view(), name="purchase_order_list"),
    path(
        "purchase-orders/create/",
        views.PurchaseOrderCreateView.as_view(),
        name="purchase_order_create",
    ),
    path(
        "purchase-orders/<uuid:pk>/",
        views.PurchaseOrderDetailView.as_view(),
        name="purchase_order_detail",
    ),
    path(
        "purchase-orders/<uuid:pk>/edit/",
        views.PurchaseOrderUpdateView.as_view(),
        name="purchase_order_edit",
    ),
    path(
        "purchase-orders/<uuid:pk>/approve/",
        views.purchase_order_approve,
        name="purchase_order_approve",
    ),
    path(
        "purchase-orders/<uuid:pk>/send/",
        views.purchase_order_send,
        name="purchase_order_send",
    ),
]
