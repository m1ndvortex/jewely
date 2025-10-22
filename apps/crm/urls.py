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
