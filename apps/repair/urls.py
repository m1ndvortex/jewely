"""
URL configuration for repair app.
"""

from django.urls import path

from . import views

app_name = "repair"

urlpatterns = [
    # Repair Order URLs
    path("", views.RepairOrderListView.as_view(), name="repair_list"),
    path("create/", views.RepairOrderCreateView.as_view(), name="repair_create"),
    path("<uuid:pk>/", views.RepairOrderDetailView.as_view(), name="repair_detail"),
    path("<uuid:pk>/edit/", views.RepairOrderUpdateView.as_view(), name="repair_edit"),
    path("<uuid:pk>/upload-photo/", views.upload_photo, name="upload_photo"),
    path("<uuid:pk>/update-status/", views.update_status, name="update_status"),
    # Work Order URLs
    path("work-order/generate/", views.generate_work_order, name="generate_work_order"),
    # Custom Order URLs
    path("custom/", views.CustomOrderListView.as_view(), name="custom_list"),
    path("custom/create/", views.CustomOrderCreateView.as_view(), name="custom_create"),
    path("custom/<uuid:pk>/", views.CustomOrderDetailView.as_view(), name="custom_detail"),
]
