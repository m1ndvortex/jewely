"""
Views for external service integration management.

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

import requests

from .integration_forms import ExternalServiceForm, OAuth2AuthorizationForm
from .integration_models import ExternalService, IntegrationHealthCheck, IntegrationLog, OAuth2Token
from .mixins import TenantRequiredMixin


class ExternalServiceListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """
    List all external service integrations for the current tenant.

    Requirement 32.9: Manage API keys for external services.
    """

    model = ExternalService
    template_name = "core/integrations/service_list.html"
    context_object_name = "services"
    paginate_by = 20

    def get_queryset(self):
        """
        Get services for current tenant only.
        """
        queryset = ExternalService.objects.filter(tenant=self.request.tenant).select_related(
            "tenant", "created_by"
        )

        # Search filter
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(provider_name__icontains=search)
                | Q(description__icontains=search)
            )

        # Service type filter
        service_type = self.request.GET.get("service_type")
        if service_type:
            queryset = queryset.filter(service_type=service_type)

        # Status filter
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        # Health filter
        health = self.request.GET.get("health")
        if health:
            queryset = queryset.filter(health_status=health.upper())

        # Order by creation date (newest first)
        queryset = queryset.order_by("-created_at")

        return queryset

    def get_context_data(self, **kwargs):
        """
        Add statistics and filter context.
        """
        context = super().get_context_data(**kwargs)

        # Get statistics
        all_services = ExternalService.objects.filter(tenant=self.request.tenant)

        context["total_services"] = all_services.count()
        context["active_services"] = all_services.filter(is_active=True).count()
        context["healthy_services"] = all_services.filter(health_status="HEALTHY").count()
        context["services_needing_attention"] = all_services.filter(
            health_status__in=["DEGRADED", "DOWN"]
        ).count()

        # Get current filters
        context["current_search"] = self.request.GET.get("search", "")
        context["current_service_type"] = self.request.GET.get("service_type", "")
        context["current_status"] = self.request.GET.get("status", "")
        context["current_health"] = self.request.GET.get("health", "")

        # Service type choices for filter
        context["service_types"] = ExternalService.SERVICE_TYPE_CHOICES

        return context


class ExternalServiceCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """
    Create a new external service integration.

    Requirement 32.9: Manage API keys for external services.
    """

    model = ExternalService
    form_class = ExternalServiceForm
    template_name = "core/integrations/service_form.html"
    success_url = reverse_lazy("core:integrations:service_list")

    def form_valid(self, form):
        """
        Set tenant and created_by before saving.
        """
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user

        response = super().form_valid(form)

        messages.success(
            self.request,
            f"Service integration '{form.instance.name}' created successfully.",
        )

        return response

    def get_context_data(self, **kwargs):
        """
        Add additional context.
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Add External Service"
        context["submit_text"] = "Create Service"
        return context


class ExternalServiceDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """
    View external service details including health and usage statistics.

    Requirement 32.9: Manage API keys for external services.
    Monitor integration health.
    """

    model = ExternalService
    template_name = "core/integrations/service_detail.html"
    context_object_name = "service"

    def get_queryset(self):
        """
        Ensure service belongs to current tenant.
        """
        return ExternalService.objects.filter(tenant=self.request.tenant).select_related(
            "tenant", "created_by"
        )

    def get_context_data(self, **kwargs):
        """
        Add health checks, logs, and statistics.
        """
        context = super().get_context_data(**kwargs)

        service = self.object

        # Get recent health checks
        recent_health_checks = IntegrationHealthCheck.objects.filter(service=service).order_by(
            "-checked_at"
        )[:20]

        context["recent_health_checks"] = recent_health_checks

        # Get recent logs
        recent_logs = IntegrationLog.objects.filter(service=service).order_by("-created_at")[:20]

        context["recent_logs"] = recent_logs

        # Calculate health statistics (last 24 hours)
        last_24h = timezone.now() - timedelta(hours=24)
        health_checks_24h = IntegrationHealthCheck.objects.filter(
            service=service, checked_at__gte=last_24h
        )

        total_checks = health_checks_24h.count()
        successful_checks = health_checks_24h.filter(status="SUCCESS").count()
        avg_response_time = health_checks_24h.aggregate(Avg("response_time_ms"))[
            "response_time_ms__avg"
        ]

        context["health_stats_24h"] = {
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "failed_checks": total_checks - successful_checks,
            "success_rate": (
                round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0
            ),
            "avg_response_time_ms": round(avg_response_time, 0) if avg_response_time else 0,
        }

        # Calculate usage statistics
        context["usage_stats"] = {
            "total_requests": service.total_requests,
            "failed_requests": service.failed_requests,
            "success_rate": service.get_success_rate(),
            "last_used": service.last_used_at,
        }

        # Check if OAuth2 token exists
        try:
            oauth2_token = service.oauth2_token
            context["has_oauth2_token"] = True
            context["oauth2_token_expired"] = oauth2_token.is_expired()
            context["oauth2_token_expiring_soon"] = oauth2_token.is_expiring_soon()
        except OAuth2Token.DoesNotExist:
            context["has_oauth2_token"] = False

        return context


class ExternalServiceUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """
    Update an existing external service integration.

    Requirement 32.9: Manage API keys for external services.
    """

    model = ExternalService
    form_class = ExternalServiceForm
    template_name = "core/integrations/service_form.html"

    def get_queryset(self):
        """
        Ensure service belongs to current tenant.
        """
        return ExternalService.objects.filter(tenant=self.request.tenant)

    def get_success_url(self):
        """
        Redirect to service detail page.
        """
        return reverse("core:integrations:service_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """
        Save service and show success message.
        """
        response = super().form_valid(form)

        messages.success(
            self.request, f"Service integration '{form.instance.name}' updated successfully."
        )

        return response

    def get_context_data(self, **kwargs):
        """
        Add additional context.
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Service Integration"
        context["submit_text"] = "Update Service"
        return context


class ExternalServiceDeleteView(LoginRequiredMixin, TenantRequiredMixin, DeleteView):
    """
    Delete an external service integration.
    """

    model = ExternalService
    template_name = "core/integrations/service_confirm_delete.html"
    success_url = reverse_lazy("core:integrations:service_list")

    def get_queryset(self):
        """
        Ensure service belongs to current tenant.
        """
        return ExternalService.objects.filter(tenant=self.request.tenant)

    def delete(self, request, *args, **kwargs):
        """
        Delete service and show success message.
        """
        service = self.get_object()
        service_name = service.name

        response = super().delete(request, *args, **kwargs)

        messages.success(request, f"Service integration '{service_name}' deleted successfully.")

        return response


class ExternalServiceToggleView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Toggle service active status.
    """

    def post(self, request, pk):
        """
        Toggle service is_active status.
        """
        service = get_object_or_404(ExternalService, pk=pk, tenant=request.tenant)

        service.is_active = not service.is_active
        service.save(update_fields=["is_active"])

        status_text = "activated" if service.is_active else "deactivated"
        messages.success(request, f"Service '{service.name}' {status_text} successfully.")

        return redirect("core:integrations:service_detail", pk=service.pk)


class ServiceHealthCheckView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Manually trigger a health check for a service.

    Monitor integration health.
    """

    def post(self, request, pk):
        """
        Perform health check and record results.
        """
        service = get_object_or_404(ExternalService, pk=pk, tenant=request.tenant)

        # Perform health check
        result = self._perform_health_check(service)

        # Record health check
        IntegrationHealthCheck.objects.create(
            service=service,
            status=result["status"],
            response_time_ms=result.get("response_time_ms"),
            status_code=result.get("status_code"),
            error_message=result.get("error_message", ""),
        )

        # Update service health status
        service.last_health_check_at = timezone.now()

        if result["status"] == "SUCCESS":
            service.consecutive_failures = 0
            service.health_status = "HEALTHY"
            service.last_error_message = ""
            messages.success(
                request,
                f"Health check passed! Response time: {result.get('response_time_ms', 0)}ms",
            )
        else:
            service.consecutive_failures += 1
            service.last_error_message = result.get("error_message", "")

            if service.consecutive_failures >= 5:
                service.health_status = "DOWN"
            elif service.consecutive_failures >= 2:
                service.health_status = "DEGRADED"

            messages.error(
                request, f"Health check failed: {result.get('error_message', 'Unknown error')}"
            )

        service.save(
            update_fields=[
                "last_health_check_at",
                "consecutive_failures",
                "health_status",
                "last_error_message",
                "updated_at",
            ]
        )

        return redirect("core:integrations:service_detail", pk=service.pk)

    def _perform_health_check(self, service):
        """
        Perform actual health check based on service type.

        Returns dict with status and details.
        """
        import time

        try:
            # If service has a base_url, try to ping it
            if service.base_url:
                start_time = time.time()
                response = requests.get(
                    service.base_url,
                    timeout=10,
                    headers={"User-Agent": "JewelryShop-HealthCheck/1.0"},
                )
                end_time = time.time()

                response_time_ms = int((end_time - start_time) * 1000)

                # Consider 2xx and 3xx as success
                if 200 <= response.status_code < 400:
                    return {
                        "status": "SUCCESS",
                        "response_time_ms": response_time_ms,
                        "status_code": response.status_code,
                    }
                else:
                    return {
                        "status": "FAILURE",
                        "response_time_ms": response_time_ms,
                        "status_code": response.status_code,
                        "error_message": f"HTTP {response.status_code}",
                    }
            else:
                # No base_url, just mark as success (can't check)
                return {
                    "status": "SUCCESS",
                    "error_message": "No base URL configured for health check",
                }

        except requests.exceptions.Timeout:
            return {
                "status": "TIMEOUT",
                "error_message": "Request timed out after 10 seconds",
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "FAILURE",
                "error_message": "Could not connect to service",
            }
        except Exception as e:
            return {
                "status": "FAILURE",
                "error_message": str(e),
            }


class IntegrationHealthDashboardView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Dashboard showing health status of all integrations.

    Monitor integration health.
    """

    def get(self, request):
        """
        Show integration health dashboard.
        """
        services = ExternalService.objects.filter(tenant=request.tenant).select_related(
            "created_by"
        )

        # Group services by health status
        healthy_services = services.filter(health_status="HEALTHY", is_active=True)
        degraded_services = services.filter(health_status="DEGRADED", is_active=True)
        down_services = services.filter(health_status="DOWN", is_active=True)
        inactive_services = services.filter(is_active=False)

        # Get recent health checks across all services
        recent_health_checks = (
            IntegrationHealthCheck.objects.filter(service__tenant=request.tenant)
            .select_related("service")
            .order_by("-checked_at")[:50]
        )

        # Calculate overall statistics
        last_24h = timezone.now() - timedelta(hours=24)
        health_checks_24h = IntegrationHealthCheck.objects.filter(
            service__tenant=request.tenant, checked_at__gte=last_24h
        )

        total_checks = health_checks_24h.count()
        successful_checks = health_checks_24h.filter(status="SUCCESS").count()

        context = {
            "healthy_services": healthy_services,
            "degraded_services": degraded_services,
            "down_services": down_services,
            "inactive_services": inactive_services,
            "recent_health_checks": recent_health_checks,
            "overall_stats": {
                "total_services": services.count(),
                "healthy_count": healthy_services.count(),
                "degraded_count": degraded_services.count(),
                "down_count": down_services.count(),
                "total_checks_24h": total_checks,
                "success_rate_24h": (
                    round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0
                ),
            },
        }

        return render(request, "core/integrations/health_dashboard.html", context)


class OAuth2InitiateView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Initiate OAuth2 authorization flow.

    Requirement 32.10: Support OAuth2 for third-party service connections.
    """

    def get(self, request, pk):
        """
        Show OAuth2 authorization form.
        """
        service = get_object_or_404(ExternalService, pk=pk, tenant=request.tenant)

        # Check if service uses OAuth2
        if service.auth_type != ExternalService.AUTH_OAUTH2:
            messages.error(request, "This service does not use OAuth2 authentication.")
            return redirect("core:integrations:service_detail", pk=service.pk)

        # Build redirect URI
        redirect_uri = request.build_absolute_uri(
            reverse("core:integrations:oauth2_callback", kwargs={"pk": service.pk})
        )

        form = OAuth2AuthorizationForm(
            initial={
                "service_id": service.id,
                "redirect_uri": redirect_uri,
            }
        )

        context = {
            "service": service,
            "form": form,
            "redirect_uri": redirect_uri,
        }

        return render(request, "core/integrations/oauth2_initiate.html", context)

    def post(self, request, pk):
        """
        Redirect to OAuth2 provider authorization URL.
        """
        service = get_object_or_404(ExternalService, pk=pk, tenant=request.tenant)

        form = OAuth2AuthorizationForm(request.POST)

        if form.is_valid():
            # Build authorization URL
            # This is a simplified example - actual implementation depends on provider
            auth_url = self._build_authorization_url(
                service, form.cleaned_data["redirect_uri"], form.cleaned_data.get("scope", "")
            )

            if auth_url:
                return redirect(auth_url)
            else:
                messages.error(
                    request, "Could not build authorization URL. Check service configuration."
                )
                return redirect("core:integrations:service_detail", pk=service.pk)

        # Form invalid
        context = {
            "service": service,
            "form": form,
        }

        return render(request, "core/integrations/oauth2_initiate.html", context)

    def _build_authorization_url(self, service, redirect_uri, scope):
        """
        Build OAuth2 authorization URL.

        This is a simplified example. Real implementation would vary by provider.
        """
        # Get authorization endpoint from service config
        auth_endpoint = service.config.get("oauth2_auth_endpoint")

        if not auth_endpoint:
            return None

        # Build URL with parameters
        import urllib.parse

        params = {
            "client_id": service.api_key,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope or service.config.get("oauth2_default_scope", ""),
            "state": str(service.id),  # Use service ID as state for verification
        }

        return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"


class OAuth2CallbackView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Handle OAuth2 callback and exchange code for tokens.

    Requirement 32.10: Support OAuth2 for third-party service connections.
    """

    def get(self, request, pk):
        """
        Handle OAuth2 callback with authorization code.
        """
        service = get_object_or_404(ExternalService, pk=pk, tenant=request.tenant)

        # Get authorization code and state from query params
        code = request.GET.get("code")
        state = request.GET.get("state")
        error = request.GET.get("error")

        # Check for errors
        if error:
            messages.error(request, f"OAuth2 authorization failed: {error}")
            return redirect("core:integrations:service_detail", pk=service.pk)

        # Verify state matches service ID
        if state != str(service.id):
            messages.error(request, "Invalid state parameter. Possible CSRF attack.")
            return redirect("core:integrations:service_detail", pk=service.pk)

        # Exchange code for tokens
        result = self._exchange_code_for_tokens(service, code, request)

        if result["success"]:
            messages.success(request, "OAuth2 authorization successful! Tokens have been saved.")
        else:
            messages.error(
                request,
                f"Failed to exchange code for tokens: {result.get('error', 'Unknown error')}",
            )

        return redirect("core:integrations:service_detail", pk=service.pk)

    def _exchange_code_for_tokens(self, service, code, request):
        """
        Exchange authorization code for access and refresh tokens.

        This is a simplified example. Real implementation would vary by provider.
        """
        try:
            # Get token endpoint from service config
            token_endpoint = service.config.get("oauth2_token_endpoint")

            if not token_endpoint:
                return {"success": False, "error": "No token endpoint configured"}

            # Build redirect URI
            redirect_uri = request.build_absolute_uri(
                reverse("core:integrations:oauth2_callback", kwargs={"pk": service.pk})
            )

            # Exchange code for tokens
            response = requests.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": service.api_key,
                    "client_secret": service.api_secret,
                },
                timeout=10,
            )

            if response.status_code == 200:
                token_data = response.json()

                # Calculate expiration time
                expires_in = token_data.get("expires_in", 3600)
                expires_at = timezone.now() + timedelta(seconds=expires_in)

                # Save or update OAuth2 token
                OAuth2Token.objects.update_or_create(
                    service=service,
                    defaults={
                        "access_token": token_data.get("access_token", ""),
                        "refresh_token": token_data.get("refresh_token", ""),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_at": expires_at,
                        "scope": token_data.get("scope", ""),
                    },
                )

                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}
