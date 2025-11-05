"""
Cached dashboard views demonstrating cache usage.

This module shows how to implement caching for expensive dashboard queries
using the cache utilities.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.core.cache_utils import (
    cache_dashboard_data,
    cache_tenant_query,
    get_cached_dashboard_data,
)
from apps.core.mixins import TenantRequiredMixin
from apps.crm.models import Customer
from apps.inventory.models import InventoryItem
from apps.repair.models import RepairOrder
from apps.sales.models import Sale

# Example: Cached query functions


@cache_tenant_query(timeout=300, key_prefix="today_sales")
def get_today_sales_data(tenant_id):
    """
    Get today's sales data with caching.

    Cached for 5 minutes (300 seconds).
    Cache is automatically invalidated when sales are created/updated.
    """
    today = timezone.now().date()

    today_sales = Sale.objects.filter(
        tenant_id=tenant_id, created_at__date=today, status=Sale.COMPLETED
    ).aggregate(total_amount=Sum("total"), total_count=Count("id"))

    # Yesterday's sales for comparison
    yesterday = today - timedelta(days=1)
    yesterday_sales = Sale.objects.filter(
        tenant_id=tenant_id, created_at__date=yesterday, status=Sale.COMPLETED
    ).aggregate(total_amount=Sum("total"))

    yesterday_amount = yesterday_sales["total_amount"] or Decimal("0.00")
    today_amount = today_sales["total_amount"] or Decimal("0.00")

    # Calculate percentage change
    if yesterday_amount > 0:
        change_percent = ((today_amount - yesterday_amount) / yesterday_amount) * 100
    else:
        change_percent = 100 if today_amount > 0 else 0

    return {
        "amount": today_amount,
        "count": today_sales["total_count"] or 0,
        "change_percent": round(change_percent, 1),
        "change_direction": "up" if change_percent >= 0 else "down",
    }


@cache_tenant_query(timeout=600, key_prefix="inventory_value")
def get_inventory_value_data(tenant_id):
    """
    Get inventory value data with caching.

    Cached for 10 minutes (600 seconds).
    Cache is automatically invalidated when inventory items change.
    """
    inventory_items = InventoryItem.objects.filter(tenant_id=tenant_id, is_active=True).values(
        "cost_price", "selling_price", "quantity"
    )

    total_cost_value = sum(item["cost_price"] * item["quantity"] for item in inventory_items)
    total_selling_value = sum(item["selling_price"] * item["quantity"] for item in inventory_items)

    stats = InventoryItem.objects.filter(tenant_id=tenant_id, is_active=True).aggregate(
        total_items=Count("id"), total_quantity=Sum("quantity")
    )

    return {
        "cost_value": total_cost_value,
        "selling_value": total_selling_value,
        "total_items": stats["total_items"] or 0,
        "total_quantity": stats["total_quantity"] or 0,
    }


@cache_tenant_query(timeout=300, key_prefix="stock_alerts")
def get_stock_alerts_data(tenant_id):
    """
    Get stock alerts data with caching.

    Cached for 5 minutes (300 seconds).
    """
    low_stock_items = InventoryItem.objects.filter(
        tenant_id=tenant_id, is_active=True, quantity__lte=F("min_quantity")
    ).count()

    out_of_stock_items = InventoryItem.objects.filter(
        tenant_id=tenant_id, is_active=True, quantity=0
    ).count()

    return {
        "low_stock_count": low_stock_items,
        "out_of_stock_count": out_of_stock_items,
        "total_alerts": low_stock_items + out_of_stock_items,
    }


@cache_tenant_query(timeout=300, key_prefix="pending_orders")
def get_pending_orders_data(tenant_id):
    """
    Get pending orders data with caching.

    Cached for 5 minutes (300 seconds).
    """
    today = timezone.now().date()

    pending_orders = RepairOrder.objects.filter(
        tenant_id=tenant_id, status__in=["received", "in_progress", "quality_check"]
    ).count()

    overdue_orders = RepairOrder.objects.filter(
        tenant_id=tenant_id,
        status__in=["received", "in_progress", "quality_check"],
        estimated_completion__lt=today,
    ).count()

    return {
        "total_pending": pending_orders,
        "overdue_count": overdue_orders,
    }


@cache_tenant_query(timeout=900, key_prefix="sales_trend")
def get_sales_trend_data(tenant_id, period="7d"):
    """
    Get sales trend data with caching.

    Cached for 15 minutes (900 seconds).
    Cache key includes the period parameter.
    """
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
                tenant_id=tenant_id,
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
                tenant_id=tenant_id,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                status=Sale.COMPLETED,
            )
            .extra(select={"month": "DATE_TRUNC('month', created_at)"})
            .values("month")
            .annotate(total_sales=Sum("total"), total_count=Count("id"))
            .order_by("month")
        )

    # Convert to list for JSON serialization
    return list(sales_data)


class CachedTenantDashboardView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """
    Cached version of tenant dashboard.

    Demonstrates how to use cached query functions in views.
    All expensive queries are cached and automatically invalidated.
    """

    template_name = "core/tenant_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        # Try to get complete dashboard data from cache
        cached_data = get_cached_dashboard_data(tenant.id)

        if cached_data:
            # Use cached data
            context.update(cached_data)
        else:
            # Build dashboard data using cached queries
            context["today_sales"] = get_today_sales_data(tenant.id)
            context["inventory_value"] = get_inventory_value_data(tenant.id)
            context["stock_alerts"] = get_stock_alerts_data(tenant.id)
            context["pending_orders"] = get_pending_orders_data(tenant.id)

            # Recent activity (not cached - always fresh)
            context["recent_sales"] = (
                Sale.objects.filter(tenant=tenant, status=Sale.COMPLETED)
                .select_related("customer", "branch", "employee")
                .order_by("-created_at")[:5]
            )

            context["recent_customers"] = Customer.objects.filter(tenant=tenant).order_by(
                "-created_at"
            )[:5]

            context["chart_data_url"] = "/api/dashboard/sales-trend/"

            # Cache the complete dashboard data
            cache_dashboard_data(tenant.id, context, timeout=300)

        return context


class CachedSalesTrendChartView(LoginRequiredMixin, TenantRequiredMixin, View):
    """
    Cached version of sales trend chart API.

    Demonstrates caching for API responses.
    """

    def get(self, request):
        tenant = request.user.tenant
        period = request.GET.get("period", "7d")

        # Get cached sales trend data
        sales_data = get_sales_trend_data(tenant.id, period)

        # Format for Chart.js
        labels = []
        values = []
        counts = []

        for item in sales_data:
            if "date" in item:
                labels.append(str(item["date"]))
            elif "month" in item:
                labels.append(str(item["month"]))

            values.append(float(item["total_sales"] or 0))
            counts.append(item["total_count"] or 0)

        return JsonResponse(
            {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Sales Amount",
                        "data": values,
                        "borderColor": "rgb(75, 192, 192)",
                        "tension": 0.1,
                    },
                    {
                        "label": "Number of Sales",
                        "data": counts,
                        "borderColor": "rgb(255, 99, 132)",
                        "tension": 0.1,
                    },
                ],
            }
        )
