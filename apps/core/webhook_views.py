"""
Views for webhook management interface.

Per Requirement 32 - Webhook and Integration Management
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime

import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .mixins import TenantRequiredMixin
from .webhook_forms import WebhookForm, WebhookTestForm
from .webhook_models import Webhook, WebhookDelivery


class WebhookListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """
    List all webhooks for the current tenant.

    Requirement 32.1: Allow tenants to register webhook URLs for event notifications.
    """

    model = Webhook
    template_name = "core/webhooks/webhook_list.html"
    context_object_name = "webhooks"
    paginate_by = 20

    def get_queryset(self):
        """
        Get webhooks for current tenant only.
        """
        queryset = Webhook.objects.filter(tenant=self.request.tenant).select_related(
            "tenant", "created_by"
        )

        # Search filter
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(url__icontains=search)
                | Q(description__icontains=search)
            )

        # Status filter
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        # Order by creation date (newest first)
        queryset = queryset.order_by("-created_at")

        return queryset

    def get_context_data(self, **kwargs):
        """
        Add additional context.
        """
        context = super().get_context_data(**kwargs)

        # Get statistics
        context["total_webhooks"] = Webhook.objects.filter(tenant=self.request.tenant).count()
        context["active_webhooks"] = Webhook.objects.filter(
            tenant=self.request.tenant, is_active=True
        ).count()
        context["inactive_webhooks"] = Webhook.objects.filter(
            tenant=self.request.tenant, is_active=False
        ).count()

        # Get current filters
        context["current_search"] = self.request.GET.get("search", "")
        context["current_status"] = self.request.GET.get("status", "")

        return context


class WebhookCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """
    Create a new webhook.

    Requirement 32.1: Allow tenants to register webhook URLs for event notifications.
    Requirement 32.2: Allow tenants to select which events trigger webhooks.
    Requirement 32.3: Sign webhook payloads with HMAC for verification.
    """

    model = Webhook
    form_class = WebhookForm
    template_name = "core/webhooks/webhook_form.html"
    success_url = reverse_lazy("core:webhook_list")

    def form_valid(self, form):
        """
        Set tenant and created_by before saving.
        """
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user

        # Secret is auto-generated in model's save method
        response = super().form_valid(form)

        messages.success(
            self.request,
            f"Webhook '{form.instance.name}' created successfully. "
            f"Your HMAC secret has been generated.",
        )

        return response

    def get_context_data(self, **kwargs):
        """
        Add additional context.
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Webhook"
        context["submit_text"] = "Create Webhook"
        return context


class WebhookDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """
    View webhook details including delivery history.

    Requirement 32.5: Track webhook delivery status (success, failed, pending).
    Requirement 32.6: Provide detailed logs of all webhook attempts.
    """

    model = Webhook
    template_name = "core/webhooks/webhook_detail.html"
    context_object_name = "webhook"

    def get_queryset(self):
        """
        Ensure webhook belongs to current tenant.
        """
        return Webhook.objects.filter(tenant=self.request.tenant).select_related(
            "tenant", "created_by"
        )

    def get_context_data(self, **kwargs):
        """
        Add delivery history and statistics.
        """
        context = super().get_context_data(**kwargs)

        webhook = self.object

        # Get recent deliveries
        recent_deliveries = (
            WebhookDelivery.objects.filter(webhook=webhook)
            .select_related("webhook")
            .order_by("-created_at")[:20]
        )

        context["recent_deliveries"] = recent_deliveries

        # Get delivery statistics
        total_deliveries = WebhookDelivery.objects.filter(webhook=webhook).count()
        successful_deliveries = WebhookDelivery.objects.filter(
            webhook=webhook, status=WebhookDelivery.SUCCESS
        ).count()
        failed_deliveries = WebhookDelivery.objects.filter(
            webhook=webhook, status=WebhookDelivery.FAILED
        ).count()
        pending_deliveries = WebhookDelivery.objects.filter(
            webhook=webhook, status__in=[WebhookDelivery.PENDING, WebhookDelivery.RETRYING]
        ).count()

        context["delivery_stats"] = {
            "total": total_deliveries,
            "successful": successful_deliveries,
            "failed": failed_deliveries,
            "pending": pending_deliveries,
            "success_rate": (
                round((successful_deliveries / total_deliveries) * 100, 1)
                if total_deliveries > 0
                else 0
            ),
        }

        # Get event display names
        context["event_display_names"] = webhook.get_event_display_names()

        return context


class WebhookUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """
    Update an existing webhook.

    Requirement 32.1: Allow tenants to register webhook URLs for event notifications.
    Requirement 32.2: Allow tenants to select which events trigger webhooks.
    """

    model = Webhook
    form_class = WebhookForm
    template_name = "core/webhooks/webhook_form.html"

    def get_queryset(self):
        """
        Ensure webhook belongs to current tenant.
        """
        return Webhook.objects.filter(tenant=self.request.tenant)

    def get_success_url(self):
        """
        Redirect to webhook detail page.
        """
        return reverse("core:webhook_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """
        Save webhook and show success message.
        """
        response = super().form_valid(form)

        messages.success(self.request, f"Webhook '{form.instance.name}' updated successfully.")

        return response

    def get_context_data(self, **kwargs):
        """
        Add additional context.
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Webhook"
        context["submit_text"] = "Update Webhook"
        return context


class WebhookDeleteView(LoginRequiredMixin, TenantRequiredMixin, DeleteView):
    """
    Delete a webhook.
    """

    model = Webhook
    template_name = "core/webhooks/webhook_confirm_delete.html"
    success_url = reverse_lazy("core:webhook_list")

    def get_queryset(self):
        """
        Ensure webhook belongs to current tenant.
        """
        return Webhook.objects.filter(tenant=self.request.tenant)

    def delete(self, request, *args, **kwargs):
        """
        Delete webhook and show success message.
        """
        webhook = self.get_object()
        webhook_name = webhook.name

        response = super().delete(request, *args, **kwargs)

        messages.success(request, f"Webhook '{webhook_name}' deleted successfully.")

        return response


class WebhookToggleView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Toggle webhook active status.
    """

    def post(self, request, pk):
        """
        Toggle webhook is_active status.
        """
        webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)

        webhook.is_active = not webhook.is_active
        webhook.save(update_fields=["is_active", "updated_at"])

        status_text = "activated" if webhook.is_active else "deactivated"
        messages.success(request, f"Webhook '{webhook.name}' {status_text} successfully.")

        return redirect("core:webhook_detail", pk=webhook.pk)


class WebhookRegenerateSecretView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Regenerate HMAC secret for a webhook.

    Requirement 32.3: Sign webhook payloads with HMAC for verification.
    """

    def post(self, request, pk):
        """
        Generate a new HMAC secret.
        """
        webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)

        # Generate new secret
        import secrets

        webhook.secret = secrets.token_urlsafe(48)
        webhook.save(update_fields=["secret", "updated_at"])

        messages.success(
            request,
            f"New HMAC secret generated for webhook '{webhook.name}'. "
            f"Make sure to update your webhook endpoint with the new secret.",
        )

        return redirect("core:webhook_detail", pk=webhook.pk)


class WebhookTestView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Test webhook delivery.

    Requirement 32.8: Provide webhook testing capability before activation.
    """

    def get(self, request, pk):
        """
        Show webhook test form.
        """
        webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
        form = WebhookTestForm()

        context = {
            "webhook": webhook,
            "form": form,
        }

        return render(request, "core/webhooks/webhook_test.html", context)

    def post(self, request, pk):
        """
        Send test webhook delivery.
        """
        webhook = get_object_or_404(Webhook, pk=pk, tenant=request.tenant)
        form = WebhookTestForm(request.POST)

        if form.is_valid():
            event_type = form.cleaned_data["event_type"]
            test_payload = form.cleaned_data.get("test_payload")

            # Use provided payload or generate default test payload
            if not test_payload:
                test_payload = self._generate_test_payload(event_type)

            # Send test delivery
            result = self._send_test_delivery(webhook, event_type, test_payload)

            if result["success"]:
                messages.success(
                    request,
                    f"Test webhook sent successfully! "
                    f"Status: {result['status_code']}, "
                    f"Duration: {result['duration_ms']}ms",
                )
            else:
                messages.error(request, f"Test webhook failed: {result['error']}")

            # Show result details
            context = {
                "webhook": webhook,
                "form": form,
                "test_result": result,
            }

            return render(request, "core/webhooks/webhook_test.html", context)

        # Form invalid
        context = {
            "webhook": webhook,
            "form": form,
        }

        return render(request, "core/webhooks/webhook_test.html", context)

    def _generate_test_payload(self, event_type):
        """
        Generate a default test payload for the event type.
        """
        base_payload = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "test": True,
        }

        # Add event-specific data
        if "sale" in event_type:
            base_payload["data"] = {
                "sale_number": "TEST-001",
                "total": 1299.99,
                "customer_name": "Test Customer",
            }
        elif "inventory" in event_type:
            base_payload["data"] = {
                "sku": "TEST-SKU-001",
                "name": "Test Gold Ring",
                "quantity": 5,
            }
        elif "customer" in event_type:
            base_payload["data"] = {
                "customer_number": "CUST-001",
                "name": "Test Customer",
                "email": "test@example.com",
            }
        else:
            base_payload["data"] = {"message": "Test event data"}

        return base_payload

    def _send_test_delivery(self, webhook, event_type, payload):
        """
        Send a test webhook delivery.

        Returns dict with success status and details.
        """
        try:
            # Prepare payload
            payload_json = json.dumps(payload)

            # Generate HMAC signature
            signature = hmac.new(
                webhook.secret.encode("utf-8"),
                payload_json.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Event": event_type,
                "X-Webhook-ID": str(webhook.id),
                "User-Agent": "JewelryShop-Webhook/1.0",
            }

            # Send request with timeout
            start_time = timezone.now()
            response = requests.post(webhook.url, json=payload, headers=headers, timeout=10)
            end_time = timezone.now()

            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Check if successful (2xx status code)
            success = 200 <= response.status_code < 300

            return {
                "success": success,
                "status_code": response.status_code,
                "response_body": response.text[:1000],  # Truncate
                "duration_ms": duration_ms,
                "signature": signature,
                "payload": payload,
            }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out after 10 seconds",
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Could not connect to webhook URL",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class WebhookDeliveryListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """
    List webhook deliveries for a specific webhook.

    Requirement 32.5: Track webhook delivery status (success, failed, pending).
    Requirement 32.6: Provide detailed logs of all webhook attempts.
    """

    model = WebhookDelivery
    template_name = "core/webhooks/webhook_delivery_list.html"
    context_object_name = "deliveries"
    paginate_by = 50

    def get_queryset(self):
        """
        Get deliveries for the specified webhook.
        """
        webhook_id = self.kwargs.get("webhook_id")
        webhook = get_object_or_404(Webhook, pk=webhook_id, tenant=self.request.tenant)

        queryset = WebhookDelivery.objects.filter(webhook=webhook).select_related("webhook")

        # Status filter
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Event type filter
        event_type = self.request.GET.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Order by creation date (newest first)
        queryset = queryset.order_by("-created_at")

        return queryset

    def get_context_data(self, **kwargs):
        """
        Add webhook and filter context.
        """
        context = super().get_context_data(**kwargs)

        webhook_id = self.kwargs.get("webhook_id")
        webhook = get_object_or_404(Webhook, pk=webhook_id, tenant=self.request.tenant)

        context["webhook"] = webhook
        context["current_status"] = self.request.GET.get("status", "")
        context["current_event_type"] = self.request.GET.get("event_type", "")

        # Get unique event types for filter
        context["event_types"] = (
            WebhookDelivery.objects.filter(webhook=webhook)
            .values_list("event_type", flat=True)
            .distinct()
        )

        return context


class WebhookDeliveryDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """
    View detailed information about a webhook delivery.

    Requirement 32.6: Provide detailed logs of all webhook attempts.
    """

    model = WebhookDelivery
    template_name = "core/webhooks/webhook_delivery_detail.html"
    context_object_name = "delivery"

    def get_queryset(self):
        """
        Ensure delivery belongs to tenant's webhook.
        """
        return WebhookDelivery.objects.filter(webhook__tenant=self.request.tenant).select_related(
            "webhook"
        )

    def get_context_data(self, **kwargs):
        """
        Add formatted payload and retry info.
        """
        context = super().get_context_data(**kwargs)

        delivery = self.object

        # Format payload as pretty JSON
        try:
            context["formatted_payload"] = json.dumps(delivery.payload, indent=2)
        except (TypeError, ValueError):
            context["formatted_payload"] = str(delivery.payload)

        # Get retry information
        context["retry_info"] = delivery.get_retry_info()

        return context
