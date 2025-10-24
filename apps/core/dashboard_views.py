"""
Dashboard views for the jewelry shop SaaS platform.

Implements Task 12.3: Create interactive dashboards
- Tenant dashboard with KPIs (today's sales, inventory value, low stock, pending orders)
- Sales trend charts using Chart.js
- Drill-down capabilities
- Period-over-period comparison
- Requirements: 15
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, F, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.core.mixins import TenantRequiredMixin
from apps.crm.models import Customer
from apps.inventory.models import InventoryItem
from apps.repair.models import RepairOrder
from apps.sales.models import Sale


class TenantDashboardView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """
    Main tenant dashboard with KPIs and overview widgets.

    Implements Task 12.3: Create interactive dashboards
    - Today's sales widget
    - Inventory value widget
    - Low stock alerts widget
    - Pending orders widget
    - Quick actions
    - Sales trend chart
    """

    template_name = "core/tenant_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        today = timezone.now().date()

        # Today's Sales KPI
        today_sales = Sale.objects.filter(
            tenant=tenant, created_at__date=today, status=Sale.COMPLETED
        ).aggregate(total_amount=Sum("total"), total_count=Count("id"))

        context["today_sales"] = {
            "amount": today_sales["total_amount"] or Decimal("0.00"),
            "count": today_sales["total_count"] or 0,
        }

        # Yesterday's sales for comparison
        yesterday = today - timedelta(days=1)
        yesterday_sales = Sale.objects.filter(
            tenant=tenant, created_at__date=yesterday, status=Sale.COMPLETED
        ).aggregate(total_amount=Sum("total"))

        yesterday_amount = yesterday_sales["total_amount"] or Decimal("0.00")
        today_amount = context["today_sales"]["amount"]

        # Calculate percentage change
        if yesterday_amount > 0:
            change_percent = ((today_amount - yesterday_amount) / yesterday_amount) * 100
        else:
            change_percent = 100 if today_amount > 0 else 0

        context["today_sales"]["change_percent"] = round(change_percent, 1)
        context["today_sales"]["change_direction"] = "up" if change_percent >= 0 else "down"

        # Inventory Value KPI
        inventory_stats = InventoryItem.objects.filter(tenant=tenant, is_active=True).aggregate(
            total_cost_value=Sum("cost_price") * Sum("quantity"),
            total_selling_value=Sum("selling_price") * Sum("quantity"),
            total_items=Count("id"),
            total_quantity=Sum("quantity"),
        )

        # Calculate inventory value properly
        inventory_items = InventoryItem.objects.filter(tenant=tenant, is_active=True).values(
            "cost_price", "selling_price", "quantity"
        )

        total_cost_value = sum(item["cost_price"] * item["quantity"] for item in inventory_items)
        total_selling_value = sum(
            item["selling_price"] * item["quantity"] for item in inventory_items
        )

        context["inventory_value"] = {
            "cost_value": total_cost_value,
            "selling_value": total_selling_value,
            "total_items": inventory_stats["total_items"] or 0,
            "total_quantity": inventory_stats["total_quantity"] or 0,
        }

        # Low Stock Alerts KPI
        low_stock_items = InventoryItem.objects.filter(
            tenant=tenant, is_active=True, quantity__lte=F("min_quantity")
        ).count()

        out_of_stock_items = InventoryItem.objects.filter(
            tenant=tenant, is_active=True, quantity=0
        ).count()

        context["stock_alerts"] = {
            "low_stock_count": low_stock_items,
            "out_of_stock_count": out_of_stock_items,
            "total_alerts": low_stock_items + out_of_stock_items,
        }

        # Pending Orders KPI (Repair Orders)
        pending_orders = RepairOrder.objects.filter(
            tenant=tenant, status__in=["received", "in_progress", "quality_check"]
        ).count()

        overdue_orders = RepairOrder.objects.filter(
            tenant=tenant,
            status__in=["received", "in_progress", "quality_check"],
            estimated_completion__lt=today,
        ).count()

        context["pending_orders"] = {
            "total_pending": pending_orders,
            "overdue_count": overdue_orders,
        }

        # Recent Activity
        context["recent_sales"] = (
            Sale.objects.filter(tenant=tenant, status=Sale.COMPLETED)
            .select_related("customer", "branch", "employee")
            .order_by("-created_at")[:5]
        )

        context["recent_customers"] = Customer.objects.filter(tenant=tenant).order_by(
            "-created_at"
        )[:5]

        # Quick Stats for Charts
        context["chart_data_url"] = "/api/dashboard/sales-trend/"

        return context


class SalesTrendChartView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    API endpoint for sales trend chart data.

    Implements Task 12.3: Create interactive dashboards
    - Sales trend charts using Chart.js
    - Period-over-period comparison
    """

    def get(self, request):
        tenant = request.user.tenant
        period = request.GET.get("period", "7d")  # 7d, 30d, 90d, 1y

        # Calculate date range based on period
        end_date = timezone.now().date()

        if period == "7d":
            start_date = end_date - timedelta(days=7)
            group_by = "date"
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
            group_by = "date"
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
            group_by = "date"
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
            group_by = "month"
        else:
            start_date = end_date - timedelta(days=7)
            group_by = "date"

        # Get sales data
        if group_by == "date":
            sales_data = (
                Sale.objects.filter(
                    tenant=tenant,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                    status=Sale.COMPLETED,
                )
                .extra(select={"date": "DATE(created_at)"})
                .values("date")
                .annotate(total_sales=Sum("total"), total_count=Count("id"))
                .order_by("date")
            )
        else:  # group_by == 'month'
            sales_data = (
                Sale.objects.filter(
                    tenant=tenant,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                    status=Sale.COMPLETED,
                )
                .extra(select={"month": "TO_CHAR(created_at, 'YYYY-MM')"})
                .values("month")
                .annotate(total_sales=Sum("total"), total_count=Count("id"))
                .order_by("month")
            )

        # Format data for Chart.js
        labels = []
        sales_amounts = []
        sales_counts = []

        for item in sales_data:
            if group_by == "date":
                labels.append(item["date"].strftime("%m/%d"))
            else:  # month
                labels.append(item["month"])
            sales_amounts.append(float(item["total_sales"] or 0))
            sales_counts.append(item["total_count"])

        # Get comparison period data for period-over-period
        comparison_start = start_date - (end_date - start_date)
        comparison_end = start_date - timedelta(days=1)

        comparison_sales = Sale.objects.filter(
            tenant=tenant,
            created_at__date__gte=comparison_start,
            created_at__date__lte=comparison_end,
            status=Sale.COMPLETED,
        ).aggregate(total_amount=Sum("total"), total_count=Count("id"))

        current_total = sum(sales_amounts)
        comparison_total = float(comparison_sales["total_amount"] or 0)

        # Calculate percentage change
        if comparison_total > 0:
            change_percent = ((current_total - comparison_total) / comparison_total) * 100
        else:
            change_percent = 100 if current_total > 0 else 0

        return JsonResponse(
            {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Sales Amount",
                        "data": sales_amounts,
                        "borderColor": "rgb(59, 130, 246)",
                        "backgroundColor": "rgba(59, 130, 246, 0.1)",
                        "tension": 0.4,
                        "fill": True,
                    }
                ],
                "comparison": {
                    "current_total": current_total,
                    "previous_total": comparison_total,
                    "change_percent": round(change_percent, 1),
                    "change_direction": "up" if change_percent >= 0 else "down",
                },
                "period": period,
            }
        )


class InventoryDrillDownView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    API endpoint for inventory drill-down data.

    Implements Task 12.3: Create interactive dashboards
    - Drill-down capabilities for inventory analysis
    """

    def get(self, request):
        tenant = request.user.tenant
        category_id = request.GET.get("category_id")
        branch_id = request.GET.get("branch_id")

        # Base queryset
        queryset = InventoryItem.objects.filter(tenant=tenant, is_active=True)

        # Apply filters
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        # Get inventory breakdown
        inventory_data = queryset.values("category__name", "branch__name").annotate(
            total_items=Count("id"),
            total_quantity=Sum("quantity"),
            total_cost_value=Sum("cost_price") * Sum("quantity"),
            total_selling_value=Sum("selling_price") * Sum("quantity"),
            low_stock_items=Count("id", filter=Q(quantity__lte=F("min_quantity"))),
        )

        # Format data
        drill_down_data = []
        for item in inventory_data:
            drill_down_data.append(
                {
                    "category": item["category__name"],
                    "branch": item["branch__name"],
                    "total_items": item["total_items"],
                    "total_quantity": item["total_quantity"],
                    "total_cost_value": float(item["total_cost_value"] or 0),
                    "total_selling_value": float(item["total_selling_value"] or 0),
                    "low_stock_items": item["low_stock_items"],
                }
            )

        return JsonResponse(
            {
                "data": drill_down_data,
                "filters": {"category_id": category_id, "branch_id": branch_id},
            }
        )


class SalesDrillDownView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    API endpoint for sales drill-down data.

    Implements Task 12.3: Create interactive dashboards
    - Drill-down capabilities for sales analysis
    """

    def get(self, request):
        tenant = request.user.tenant
        period = request.GET.get("period", "30d")
        branch_id = request.GET.get("branch_id")
        employee_id = request.GET.get("employee_id")

        # Calculate date range
        end_date = timezone.now().date()
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)

        # Base queryset
        queryset = Sale.objects.filter(
            tenant=tenant,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status=Sale.COMPLETED,
        )

        # Apply filters
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # Get sales breakdown
        sales_data = (
            queryset.values(
                "branch__name", "employee__first_name", "employee__last_name", "payment_method"
            )
            .annotate(
                total_sales=Sum("total"), total_count=Count("id"), avg_sale_amount=Avg("total")
            )
            .order_by("-total_sales")
        )

        # Format data
        drill_down_data = []
        for item in sales_data:
            drill_down_data.append(
                {
                    "branch": item["branch__name"],
                    "employee": f"{item['employee__first_name']} {item['employee__last_name']}",
                    "payment_method": item["payment_method"],
                    "total_sales": float(item["total_sales"]),
                    "total_count": item["total_count"],
                    "avg_sale_amount": float(item["avg_sale_amount"]),
                }
            )

        return JsonResponse(
            {
                "data": drill_down_data,
                "period": period,
                "filters": {"branch_id": branch_id, "employee_id": employee_id},
            }
        )


class DashboardStatsView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    API endpoint for real-time dashboard statistics.

    Implements Task 12.3: Create interactive dashboards
    - Real-time KPI updates
    """

    def get(self, request):
        tenant = request.user.tenant
        today = timezone.now().date()

        # Get current stats
        stats = {
            "today_sales": Sale.objects.filter(
                tenant=tenant, created_at__date=today, status=Sale.COMPLETED
            ).aggregate(total=Sum("total"), count=Count("id")),
            "total_customers": Customer.objects.filter(tenant=tenant).count(),
            "active_inventory": InventoryItem.objects.filter(tenant=tenant, is_active=True).count(),
            "pending_orders": RepairOrder.objects.filter(
                tenant=tenant, status__in=["received", "in_progress", "quality_check"]
            ).count(),
        }

        # Format response
        return JsonResponse(
            {
                "today_sales_amount": float(stats["today_sales"]["total"] or 0),
                "today_sales_count": stats["today_sales"]["count"],
                "total_customers": stats["total_customers"],
                "active_inventory": stats["active_inventory"],
                "pending_orders": stats["pending_orders"],
                "timestamp": timezone.now().isoformat(),
            }
        )
