"""
Views for the reporting system.

Implements Requirement 15: Advanced Reporting and Analytics
- Report management views
- Pre-built report execution
- Report scheduling and dashboard
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.core.mixins import TenantRequiredMixin
from apps.reporting.models import Report, ReportExecution, ReportSchedule
from apps.reporting.services import PrebuiltReportService, ReportExecutionService
from apps.reporting.tasks import execute_report_async


class ReportListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """List all reports for the current tenant."""

    model = Report
    template_name = "reporting/report_list.html"
    context_object_name = "reports"
    paginate_by = 20

    def get_queryset(self):
        return (
            Report.objects.filter(tenant=self.request.user.tenant)
            .select_related("category", "created_by")
            .order_by("-updated_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = (
            Report.objects.filter(tenant=self.request.user.tenant)
            .values_list("category__name", flat=True)
            .distinct()
        )
        return context


class ReportDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """Display report details and execution history."""

    model = Report
    template_name = "reporting/report_detail.html"
    context_object_name = "report"

    def get_queryset(self):
        return Report.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["executions"] = self.object.executions.order_by("-started_at")[:10]
        context["schedules"] = self.object.schedules.filter(status="ACTIVE")
        return context


class ReportCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """Create a new custom report."""

    model = Report
    template_name = "reporting/report_form.html"
    fields = ["name", "description", "category", "query_config", "parameters", "output_formats"]

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        form.instance.report_type = "CUSTOM"
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("reporting:report_detail", kwargs={"pk": self.object.pk})


class ReportUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """Update an existing report."""

    model = Report
    template_name = "reporting/report_form.html"
    fields = ["name", "description", "category", "query_config", "parameters", "output_formats"]

    def get_queryset(self):
        return Report.objects.filter(tenant=self.request.user.tenant)

    def get_success_url(self):
        return reverse("reporting:report_detail", kwargs={"pk": self.object.pk})


class ReportDeleteView(LoginRequiredMixin, TenantRequiredMixin, DeleteView):
    """Delete a report."""

    model = Report
    template_name = "reporting/report_confirm_delete.html"
    success_url = reverse_lazy("reporting:report_list")

    def get_queryset(self):
        return Report.objects.filter(tenant=self.request.user.tenant)


class ReportExecuteView(LoginRequiredMixin, TenantRequiredMixin, FormView):
    """Execute a report with parameters."""

    template_name = "reporting/report_execute.html"

    def get_report(self):
        return get_object_or_404(Report, pk=self.kwargs["pk"], tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report"] = self.get_report()
        return context

    def post(self, request, *args, **kwargs):
        report = self.get_report()

        # Get parameters from form
        parameters = {}
        for key, value in request.POST.items():
            if key.startswith("param_"):
                param_name = key[6:]  # Remove 'param_' prefix
                parameters[param_name] = value

        output_format = request.POST.get("output_format", "PDF")
        email_recipients = request.POST.get("email_recipients", "").split(",")
        email_recipients = [email.strip() for email in email_recipients if email.strip()]

        try:
            # Execute report asynchronously
            execute_report_async.delay(
                tenant_id=str(request.user.tenant.id),
                report_id=str(report.id),
                parameters=parameters,
                output_format=output_format,
                user_id=request.user.id,
                email_recipients=email_recipients,
            )

            messages.success(
                request,
                f"Report '{report.name}' has been queued for execution. "
                f"You will be notified when it's complete.",
            )

            return redirect("reporting:report_detail", pk=report.pk)

        except Exception as e:
            messages.error(request, f"Failed to execute report: {str(e)}")
            return self.get(request, *args, **kwargs)


class ReportExecutionDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """Display report execution details."""

    model = ReportExecution
    template_name = "reporting/execution_detail.html"
    context_object_name = "execution"

    def get_queryset(self):
        return ReportExecution.objects.filter(
            report__tenant=self.request.user.tenant
        ).select_related("report", "executed_by")


class ReportDownloadView(LoginRequiredMixin, TenantRequiredMixin, View):
    """Download a report execution result."""

    def get(self, request, pk):
        execution = get_object_or_404(
            ReportExecution, pk=pk, report__tenant=request.user.tenant, status="COMPLETED"
        )

        if not execution.result_file_path or not execution.result_file_path.strip():
            messages.error(request, "Report file not found or has been cleaned up.")
            return redirect("reporting:execution_detail", pk=pk)

        try:
            import os

            if not os.path.exists(execution.result_file_path):
                messages.error(request, "Report file not found on disk.")
                return redirect("reporting:execution_detail", pk=pk)

            with open(execution.result_file_path, "rb") as f:
                response = HttpResponse(f.read())

            # Set content type based on format
            content_types = {
                "PDF": "application/pdf",
                "EXCEL": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "CSV": "text/csv",
                "JSON": "application/json",
            }

            response["Content-Type"] = content_types.get(
                execution.output_format, "application/octet-stream"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{os.path.basename(execution.result_file_path)}"'
            )

            return response

        except Exception as e:
            messages.error(request, f"Failed to download report: {str(e)}")
            return redirect("reporting:execution_detail", pk=pk)


class PrebuiltReportsView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """Display available pre-built reports."""

    template_name = "reporting/prebuilt_reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        reports = PrebuiltReportService.get_prebuilt_reports()

        # Group reports by category
        categories = {}
        for report in reports:
            category = report["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(report)

        context["categories"] = categories
        return context


class BasePrebuiltReportView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """Base view for pre-built reports."""

    template_name = "reporting/prebuilt_report.html"
    report_id = None

    def get_report_definition(self):
        if not self.report_id:
            raise NotImplementedError("report_id must be set")
        return PrebuiltReportService.get_prebuilt_report(self.report_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_def"] = self.get_report_definition()
        return context

    def post(self, request, *args, **kwargs):
        report_def = self.get_report_definition()

        # Get parameters from form
        parameters = {}
        for key, value in request.POST.items():
            if key.startswith("param_"):
                param_name = key[6:]  # Remove 'param_' prefix
                if value:  # Only include non-empty values
                    parameters[param_name] = value

        # Handle date ranges
        if "param_date_range_start" in request.POST and "param_date_range_end" in request.POST:
            parameters["date_range_start"] = request.POST["param_date_range_start"]
            parameters["date_range_end"] = request.POST["param_date_range_end"]

        output_format = request.POST.get("output_format", "PDF")
        email_recipients = request.POST.get("email_recipients", "").split(",")
        email_recipients = [email.strip() for email in email_recipients if email.strip()]

        try:
            # Create or get the report instance
            report, created = Report.objects.get_or_create(
                tenant=request.user.tenant,
                query_config__report_name=self.report_id,
                defaults={
                    "name": report_def["name"],
                    "description": report_def["description"],
                    "report_type": "PREDEFINED",
                    "query_config": {"report_name": self.report_id},
                    "parameters": {"parameters": report_def["parameters"]},
                    "output_formats": report_def["output_formats"],
                    "created_by": request.user,
                    "is_public": True,
                },
            )

            # Execute report
            execution_service = ReportExecutionService(request.user.tenant)
            execution = execution_service.execute_report(
                report=report,
                parameters=parameters,
                output_format=output_format,
                user=request.user,
                email_recipients=email_recipients,
            )

            messages.success(
                request,
                f"Report '{report_def['name']}' executed successfully. "
                f"{execution.row_count} rows generated.",
            )

            return redirect("reporting:execution_detail", pk=execution.pk)

        except Exception as e:
            messages.error(request, f"Failed to execute report: {str(e)}")
            return self.get(request, *args, **kwargs)


# Sales Reports
class SalesSummaryReportView(BasePrebuiltReportView):
    report_id = "sales_summary"


class SalesByProductReportView(BasePrebuiltReportView):
    report_id = "sales_by_product"


class SalesByEmployeeReportView(BasePrebuiltReportView):
    report_id = "sales_by_employee"


class SalesByBranchReportView(BasePrebuiltReportView):
    report_id = "sales_by_branch"


# Inventory Reports
class InventoryValuationReportView(BasePrebuiltReportView):
    report_id = "inventory_valuation"


class InventoryTurnoverReportView(BasePrebuiltReportView):
    report_id = "inventory_turnover"


class DeadStockReportView(BasePrebuiltReportView):
    report_id = "dead_stock"


# Financial Reports
class FinancialSummaryReportView(BasePrebuiltReportView):
    report_id = "financial_summary"


class RevenueTrendsReportView(BasePrebuiltReportView):
    report_id = "revenue_trends"


class ExpenseBreakdownReportView(BasePrebuiltReportView):
    report_id = "expense_breakdown"


# Customer Reports
class TopCustomersReportView(BasePrebuiltReportView):
    report_id = "top_customers"


class CustomerAcquisitionReportView(BasePrebuiltReportView):
    report_id = "customer_acquisition"


class LoyaltyAnalyticsReportView(BasePrebuiltReportView):
    report_id = "loyalty_analytics"


# Report Scheduling Views
class ReportScheduleListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """List all report schedules."""

    model = ReportSchedule
    template_name = "reporting/schedule_list.html"
    context_object_name = "schedules"
    paginate_by = 20

    def get_queryset(self):
        return (
            ReportSchedule.objects.filter(report__tenant=self.request.user.tenant)
            .select_related("report", "created_by")
            .order_by("-created_at")
        )


class ReportScheduleCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """Create a new report schedule."""

    model = ReportSchedule
    template_name = "reporting/schedule_form.html"
    fields = [
        "name",
        "description",
        "frequency",
        "cron_expression",
        "start_date",
        "end_date",
        "parameters",
        "output_format",
        "email_recipients",
        "email_subject",
        "email_body",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reports"] = Report.objects.filter(tenant=self.request.user.tenant).order_by("name")
        return context

    def form_valid(self, form):
        report_id = self.request.POST.get("report")
        form.instance.report = get_object_or_404(
            Report, pk=report_id, tenant=self.request.user.tenant
        )
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("reporting:schedule_detail", kwargs={"pk": self.object.pk})


class ReportScheduleDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """Display schedule details and execution history."""

    model = ReportSchedule
    template_name = "reporting/schedule_detail.html"
    context_object_name = "schedule"

    def get_queryset(self):
        return ReportSchedule.objects.filter(
            report__tenant=self.request.user.tenant
        ).select_related("report", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["executions"] = self.object.executions.order_by("-started_at")[:10]
        return context


class ReportScheduleUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """Update a report schedule."""

    model = ReportSchedule
    template_name = "reporting/schedule_form.html"
    fields = [
        "name",
        "description",
        "frequency",
        "cron_expression",
        "start_date",
        "end_date",
        "parameters",
        "output_format",
        "email_recipients",
        "email_subject",
        "email_body",
        "status",
    ]

    def get_queryset(self):
        return ReportSchedule.objects.filter(report__tenant=self.request.user.tenant)

    def get_success_url(self):
        return reverse("reporting:schedule_detail", kwargs={"pk": self.object.pk})


class ReportScheduleDeleteView(LoginRequiredMixin, TenantRequiredMixin, DeleteView):
    """Delete a report schedule."""

    model = ReportSchedule
    template_name = "reporting/schedule_confirm_delete.html"
    success_url = reverse_lazy("reporting:schedule_list")

    def get_queryset(self):
        return ReportSchedule.objects.filter(report__tenant=self.request.user.tenant)


class ReportDashboardView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """Report dashboard with statistics and recent activity."""

    template_name = "reporting/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        # Get statistics
        context["total_reports"] = Report.objects.filter(tenant=tenant).count()
        context["active_schedules"] = ReportSchedule.objects.filter(
            report__tenant=tenant, status="ACTIVE"
        ).count()

        # Recent executions
        context["recent_executions"] = (
            ReportExecution.objects.filter(report__tenant=tenant)
            .select_related("report", "executed_by")
            .order_by("-started_at")[:10]
        )

        # Execution statistics for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        executions_last_30_days = ReportExecution.objects.filter(
            report__tenant=tenant, started_at__gte=thirty_days_ago
        )

        context["executions_last_30_days"] = executions_last_30_days.count()
        context["successful_executions"] = executions_last_30_days.filter(
            status="COMPLETED"
        ).count()
        context["failed_executions"] = executions_last_30_days.filter(status="FAILED").count()

        # Most popular reports
        from django.db.models import Count

        context["popular_reports"] = (
            Report.objects.filter(tenant=tenant)
            .annotate(execution_count=Count("executions"))
            .order_by("-execution_count")[:5]
        )

        # Pre-built reports
        context["prebuilt_categories"] = {
            "SALES": PrebuiltReportService.get_reports_by_category("SALES")[:3],
            "INVENTORY": PrebuiltReportService.get_reports_by_category("INVENTORY")[:3],
            "FINANCIAL": PrebuiltReportService.get_reports_by_category("FINANCIAL")[:3],
            "CUSTOMER": PrebuiltReportService.get_reports_by_category("CUSTOMER")[:3],
        }

        return context
