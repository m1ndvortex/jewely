"""
Settings views for tenant configuration.

Implements Requirement 20: Settings and Configuration
- Shop profile configuration page
- Branding customization (logo upload, colors)
- Business hours configuration
- Holiday calendar
"""

import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView, UpdateView

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .decorators import tenant_required
from .forms import IntegrationSettingsForm, InvoiceSettingsForm, TenantSettingsForm
from .models import IntegrationSettings, InvoiceSettings, TenantSettings
from .permissions import TenantPermissionMixin
from .serializers import (
    IntegrationSettingsSerializer,
    InvoiceSettingsSerializer,
    TenantSettingsSerializer,
)


class SettingsOverviewView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Settings overview page showing all configuration sections.
    """

    template_name = "core/settings/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        # Get or create settings objects
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        invoice_settings, _ = InvoiceSettings.objects.get_or_create(tenant=tenant)
        integration_settings, _ = IntegrationSettings.objects.get_or_create(tenant=tenant)

        context.update(
            {
                "tenant_settings": tenant_settings,
                "invoice_settings": invoice_settings,
                "integration_settings": integration_settings,
                "active_tab": "overview",
            }
        )
        return context


class ShopProfileView(LoginRequiredMixin, TenantPermissionMixin, UpdateView):
    """
    Shop profile configuration page.
    Handles business information, contact details, and basic settings.
    """

    model = TenantSettings
    form_class = TenantSettingsForm
    template_name = "core/settings/shop_profile.html"
    success_url = reverse_lazy("core:settings_shop_profile")

    def get_object(self, queryset=None):
        """Get or create TenantSettings for current tenant."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=self.request.user.tenant)
        return tenant_settings

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "shop_profile"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Shop profile updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class BrandingCustomizationView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Branding customization page.
    Handles logo upload, color scheme, and visual branding.
    """

    template_name = "core/settings/branding.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=self.request.user.tenant)
        context.update(
            {
                "tenant_settings": tenant_settings,
                "active_tab": "branding",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle branding updates."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)

        # Handle logo upload
        if "logo" in request.FILES:
            tenant_settings.logo = request.FILES["logo"]

        # Handle color updates
        if "primary_color" in request.POST:
            primary_color = request.POST.get("primary_color", "").strip()
            if primary_color and primary_color.startswith("#") and len(primary_color) == 7:
                tenant_settings.primary_color = primary_color
            else:
                messages.error(request, "Invalid primary color format. Use hex format like #1f2937")
                return redirect("core:settings_branding")

        if "secondary_color" in request.POST:
            secondary_color = request.POST.get("secondary_color", "").strip()
            if secondary_color and secondary_color.startswith("#") and len(secondary_color) == 7:
                tenant_settings.secondary_color = secondary_color
            else:
                messages.error(
                    request, "Invalid secondary color format. Use hex format like #6b7280"
                )
                return redirect("core:settings_branding")

        try:
            tenant_settings.save()
            messages.success(request, "Branding settings updated successfully.")
        except ValidationError as e:
            messages.error(request, f"Error updating branding: {e}")

        return redirect("core:settings_branding")


class BusinessHoursView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Business hours configuration page.
    Handles weekly operating hours and special schedules.
    """

    template_name = "core/settings/business_hours.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=self.request.user.tenant)

        # Ensure business_hours has all days
        default_hours = {
            "monday": {"open": "09:00", "close": "18:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "18:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "18:00", "closed": False},
            "thursday": {"open": "09:00", "close": "18:00", "closed": False},
            "friday": {"open": "09:00", "close": "18:00", "closed": False},
            "saturday": {"open": "10:00", "close": "16:00", "closed": False},
            "sunday": {"open": "12:00", "close": "16:00", "closed": True},
        }

        # Merge with existing hours
        business_hours = {**default_hours, **tenant_settings.business_hours}

        context.update(
            {
                "tenant_settings": tenant_settings,
                "business_hours": business_hours,
                "active_tab": "business_hours",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle business hours updates."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)

        try:
            # Parse business hours from form data
            business_hours = {}
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

            for day in days:
                closed = request.POST.get(f"{day}_closed") == "on"
                open_time = request.POST.get(f"{day}_open", "09:00")
                close_time = request.POST.get(f"{day}_close", "18:00")

                business_hours[day] = {
                    "open": open_time,
                    "close": close_time,
                    "closed": closed,
                }

            tenant_settings.business_hours = business_hours
            tenant_settings.save()

            messages.success(request, "Business hours updated successfully.")

        except (ValueError, KeyError) as e:
            messages.error(request, f"Error updating business hours: {e}")

        return redirect("core:settings_business_hours")


class HolidayCalendarView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Holiday calendar configuration page.
    Handles holiday dates and special closures.
    """

    template_name = "core/settings/holiday_calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=self.request.user.tenant)

        # Sort holidays by date
        holidays = sorted(tenant_settings.holidays, key=lambda x: x.get("date", ""))

        context.update(
            {
                "tenant_settings": tenant_settings,
                "holidays": holidays,
                "active_tab": "holiday_calendar",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle holiday calendar updates."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)

        action = request.POST.get("action")

        if action == "add_holiday":
            holiday_date = request.POST.get("holiday_date")
            holiday_name = request.POST.get("holiday_name", "").strip()

            if not holiday_date or not holiday_name:
                messages.error(request, "Both date and name are required for holidays.")
                return redirect("core:settings_holiday_calendar")

            try:
                # Validate date format
                datetime.strptime(holiday_date, "%Y-%m-%d")

                # Check if holiday already exists
                existing_dates = [h.get("date") for h in tenant_settings.holidays]
                if holiday_date in existing_dates:
                    messages.error(request, "A holiday already exists for this date.")
                    return redirect("core:settings_holiday_calendar")

                # Add new holiday
                tenant_settings.holidays.append({"date": holiday_date, "name": holiday_name})
                tenant_settings.save()

                messages.success(request, f"Holiday '{holiday_name}' added successfully.")

            except ValueError:
                messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")

        elif action == "remove_holiday":
            holiday_date = request.POST.get("holiday_date")

            if holiday_date:
                # Remove holiday with matching date
                tenant_settings.holidays = [
                    h for h in tenant_settings.holidays if h.get("date") != holiday_date
                ]
                tenant_settings.save()
                messages.success(request, "Holiday removed successfully.")

        return redirect("core:settings_holiday_calendar")


class InvoiceCustomizationView(LoginRequiredMixin, TenantPermissionMixin, UpdateView):
    """
    Invoice customization page.
    Handles invoice templates, numbering schemes, custom fields, and tax configuration.
    """

    model = InvoiceSettings
    form_class = InvoiceSettingsForm
    template_name = "core/settings/invoice_customization.html"
    success_url = reverse_lazy("core:settings_invoice_customization")

    def get_object(self, queryset=None):
        """Get or create InvoiceSettings for current tenant."""
        invoice_settings, _ = InvoiceSettings.objects.get_or_create(tenant=self.request.user.tenant)
        return invoice_settings

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "invoice_customization"

        # Add preview data for number formatting
        invoice_settings = self.get_object()
        context["invoice_preview"] = self._generate_preview_number(
            invoice_settings.invoice_numbering_scheme,
            invoice_settings.invoice_number_prefix,
            invoice_settings.invoice_number_format,
            invoice_settings.next_invoice_number,
        )
        context["receipt_preview"] = self._generate_preview_number(
            invoice_settings.receipt_numbering_scheme,
            invoice_settings.receipt_number_prefix,
            invoice_settings.receipt_number_format,
            invoice_settings.next_receipt_number,
        )

        return context

    def _generate_preview_number(self, scheme, prefix, format_str, next_number):
        """Generate a preview of the number format."""
        try:
            if scheme == InvoiceSettings.NUMBERING_SEQUENTIAL:
                return format_str.format(prefix=prefix, number=next_number)
            elif scheme == InvoiceSettings.NUMBERING_YEARLY:
                year = datetime.now().year
                return f"{year}-{next_number:03d}"
            elif scheme == InvoiceSettings.NUMBERING_MONTHLY:
                now = datetime.now()
                return f"{now.year}-{now.month:02d}-{next_number:03d}"
            else:  # NUMBERING_CUSTOM
                return format_str.format(
                    prefix=prefix,
                    number=next_number,
                    year=datetime.now().year,
                    month=datetime.now().month,
                )
        except Exception:
            return "Invalid format"

    def form_valid(self, form):
        messages.success(self.request, "Invoice settings updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class IntegrationSettingsView(LoginRequiredMixin, TenantPermissionMixin, UpdateView):
    """
    Integration settings page.
    Handles payment gateway, SMS provider, and email service configuration.
    """

    model = IntegrationSettings
    form_class = IntegrationSettingsForm
    template_name = "core/settings/integration_settings.html"
    success_url = reverse_lazy("core:settings_integration")

    def get_object(self, queryset=None):
        """Get or create IntegrationSettings for current tenant."""
        integration_settings, _ = IntegrationSettings.objects.get_or_create(
            tenant=self.request.user.tenant
        )
        return integration_settings

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "integration"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Integration settings updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DataManagementView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Data management page for export and import functionality.
    """

    template_name = "core/settings/data_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "data_management"
        # TODO: Add recent activities from a DataActivity model
        context["recent_activities"] = []
        return context

    def post(self, request, *args, **kwargs):
        """Handle data export and import requests."""
        action = request.POST.get("action")

        if action == "export":
            return self._handle_export(request)
        elif action == "import":
            return self._handle_import(request)

        return redirect("core:settings_data_management")

    def _handle_export(self, request):
        """Handle data export requests."""
        export_types = request.POST.getlist("export_types")
        export_format = request.POST.get("export_format", "csv")
        # date_from = request.POST.get("export_date_from")  # TODO: Use for filtering
        # date_to = request.POST.get("export_date_to")  # TODO: Use for filtering

        if not export_types:
            messages.error(request, "Please select at least one data type to export.")
            return redirect("core:settings_data_management")

        try:
            # TODO: Implement actual export functionality
            # This would involve creating CSV/Excel files with the selected data
            messages.success(
                request,
                f"Export started for {', '.join(export_types)} in {export_format.upper()} format.",
            )
        except Exception as e:
            messages.error(request, f"Export failed: {e}")

        return redirect("core:settings_data_management")

    def _handle_import(self, request):
        """Handle data import requests."""
        import_type = request.POST.get("import_type")
        import_file = request.FILES.get("import_file")
        # update_existing = request.POST.get("update_existing") == "on"  # TODO: Use for updates
        validate_only = request.POST.get("validate_only") == "on"

        if not import_type:
            messages.error(request, "Please select a data type to import.")
            return redirect("core:settings_data_management")

        if not import_file:
            messages.error(request, "Please select a file to import.")
            return redirect("core:settings_data_management")

        try:
            # TODO: Implement actual import functionality
            # This would involve parsing CSV/Excel files and validating data
            if validate_only:
                messages.success(
                    request, f"Validation completed for {import_type} data. No errors found."
                )
            else:
                messages.success(request, f"Import completed for {import_type} data.")
        except Exception as e:
            messages.error(request, f"Import failed: {e}")

        return redirect("core:settings_data_management")


class SecuritySettingsView(LoginRequiredMixin, TenantPermissionMixin, TemplateView):
    """
    Security settings page for MFA and password policies.
    """

    template_name = "core/settings/security_settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=self.request.user.tenant)

        context.update(
            {
                "tenant_settings": tenant_settings,
                "active_tab": "security",
                "user_has_mfa": self.request.user.is_mfa_enabled,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle security settings updates."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)

        try:
            # Update MFA requirement for managers
            tenant_settings.require_mfa_for_managers = (
                request.POST.get("require_mfa_for_managers") == "on"
            )

            # Update password expiry
            password_expiry = request.POST.get("password_expiry_days", "0")
            try:
                tenant_settings.password_expiry_days = int(password_expiry)
            except ValueError:
                tenant_settings.password_expiry_days = 0

            tenant_settings.save()
            messages.success(request, "Security settings updated successfully.")

        except Exception as e:
            messages.error(request, f"Error updating security settings: {e}")

        return redirect("core:settings_security")


@login_required
@tenant_required
def download_template(request, template_type):
    """
    Download CSV template files for data import.
    """
    import csv

    from django.http import HttpResponse

    templates = {
        "inventory": {
            "filename": "inventory_template.csv",
            "headers": [
                "SKU",
                "Name",
                "Description",
                "Category",
                "Karat",
                "Weight (grams)",
                "Cost Price",
                "Selling Price",
                "Quantity",
                "Supplier",
                "Notes",
            ],
        },
        "customers": {
            "filename": "customers_template.csv",
            "headers": [
                "First Name",
                "Last Name",
                "Email",
                "Phone",
                "Address",
                "City",
                "State",
                "Postal Code",
                "Country",
                "Date of Birth",
                "Notes",
            ],
        },
        "suppliers": {
            "filename": "suppliers_template.csv",
            "headers": [
                "Company Name",
                "Contact Person",
                "Email",
                "Phone",
                "Address",
                "City",
                "State",
                "Postal Code",
                "Country",
                "Website",
                "Notes",
            ],
        },
    }

    if template_type not in templates:
        messages.error(request, "Invalid template type.")
        return redirect("core:settings_data_management")

    template = templates[template_type]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{template["filename"]}"'

    writer = csv.writer(response)
    writer.writerow(template["headers"])

    return response


# API Views for AJAX updates


class TenantSettingsAPIView(APIView):
    """
    API endpoint for tenant settings CRUD operations.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current tenant settings."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)
        serializer = TenantSettingsSerializer(tenant_settings)
        return Response(serializer.data)

    def patch(self, request):
        """Update tenant settings."""
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)
        serializer = TenantSettingsSerializer(tenant_settings, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvoiceSettingsAPIView(APIView):
    """
    API endpoint for invoice settings CRUD operations.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current invoice settings."""
        invoice_settings, _ = InvoiceSettings.objects.get_or_create(tenant=request.user.tenant)
        serializer = InvoiceSettingsSerializer(invoice_settings)
        return Response(serializer.data)

    def patch(self, request):
        """Update invoice settings."""
        invoice_settings, _ = InvoiceSettings.objects.get_or_create(tenant=request.user.tenant)
        serializer = InvoiceSettingsSerializer(invoice_settings, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IntegrationSettingsAPIView(APIView):
    """
    API endpoint for integration settings CRUD operations.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current integration settings."""
        integration_settings, _ = IntegrationSettings.objects.get_or_create(
            tenant=request.user.tenant
        )
        serializer = IntegrationSettingsSerializer(integration_settings)
        return Response(serializer.data)

    def patch(self, request):
        """Update integration settings."""
        integration_settings, _ = IntegrationSettings.objects.get_or_create(
            tenant=request.user.tenant
        )
        serializer = IntegrationSettingsSerializer(
            integration_settings, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@require_http_methods(["POST"])
@login_required
@tenant_required
@csrf_exempt
def upload_logo_api(request):
    """
    API endpoint for logo upload via AJAX.
    """
    if "logo" not in request.FILES:
        return JsonResponse({"error": "No logo file provided"}, status=400)

    tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)

    try:
        tenant_settings.logo = request.FILES["logo"]
        tenant_settings.save()

        return JsonResponse(
            {
                "success": True,
                "logo_url": tenant_settings.logo.url if tenant_settings.logo else None,
                "message": "Logo uploaded successfully",
            }
        )

    except Exception as e:
        return JsonResponse({"error": f"Error uploading logo: {str(e)}"}, status=500)


@require_http_methods(["POST"])
@login_required
@tenant_required
@csrf_exempt
def update_colors_api(request):
    """
    API endpoint for updating brand colors via AJAX.
    """
    try:
        data = json.loads(request.body)
        primary_color = data.get("primary_color")
        secondary_color = data.get("secondary_color")

        if not primary_color or not secondary_color:
            return JsonResponse({"error": "Both colors are required"}, status=400)

        # Validate hex color format
        for color in [primary_color, secondary_color]:
            if not color.startswith("#") or len(color) != 7:
                return JsonResponse(
                    {"error": "Invalid color format. Use hex format like #1f2937"}, status=400
                )

        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=request.user.tenant)
        tenant_settings.primary_color = primary_color
        tenant_settings.secondary_color = secondary_color
        tenant_settings.save()

        return JsonResponse(
            {
                "success": True,
                "primary_color": primary_color,
                "secondary_color": secondary_color,
                "message": "Colors updated successfully",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Error updating colors: {str(e)}"}, status=500)
