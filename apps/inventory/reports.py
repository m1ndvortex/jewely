"""
Inventory reporting functionality.

Implements Requirement 9: Advanced Inventory Management
- Inventory valuation report
- Low stock alert report
- Dead stock analysis report
- Inventory turnover report

Implements Requirement 15: Advanced Reporting and Analytics
- Pre-built reports for inventory metrics
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from .models import InventoryItem


class InventoryReportGenerator:
    """Generate various inventory reports for a tenant."""

    def __init__(self, tenant):
        """
        Initialize report generator for a specific tenant.

        Args:
            tenant: The tenant to generate reports for
        """
        self.tenant = tenant

    def get_inventory_valuation_report(self, branch_id=None, category_id=None):
        """
        Generate inventory valuation report.

        Shows total inventory value at cost and selling price,
        broken down by category and branch.

        Args:
            branch_id: Optional branch filter
            category_id: Optional category filter

        Returns:
            dict: Report data with summary and details
        """
        queryset = InventoryItem.objects.filter(tenant=self.tenant, is_active=True).select_related(
            "category", "branch"
        )

        # Apply filters
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Calculate totals
        total_items = queryset.count()
        total_quantity = queryset.aggregate(total=Sum("quantity"))["total"] or 0

        # Calculate total cost value (cost_price * quantity)
        total_cost_value = sum(item.cost_price * item.quantity for item in queryset)

        # Calculate total selling value (selling_price * quantity)
        total_selling_value = sum(item.selling_price * item.quantity for item in queryset)

        # Calculate potential profit
        potential_profit = total_selling_value - total_cost_value
        profit_margin = (
            (potential_profit / total_cost_value * 100) if total_cost_value > 0 else Decimal("0.00")
        )

        # Group by category
        category_breakdown = {}
        for item in queryset:
            cat_name = item.category.name
            if cat_name not in category_breakdown:
                category_breakdown[cat_name] = {
                    "category": cat_name,
                    "item_count": 0,
                    "total_quantity": 0,
                    "cost_value": Decimal("0.00"),
                    "selling_value": Decimal("0.00"),
                }

            category_breakdown[cat_name]["item_count"] += 1
            category_breakdown[cat_name]["total_quantity"] += item.quantity
            category_breakdown[cat_name]["cost_value"] += item.cost_price * item.quantity
            category_breakdown[cat_name]["selling_value"] += item.selling_price * item.quantity

        # Group by branch
        branch_breakdown = {}
        for item in queryset:
            branch_name = item.branch.name
            if branch_name not in branch_breakdown:
                branch_breakdown[branch_name] = {
                    "branch": branch_name,
                    "item_count": 0,
                    "total_quantity": 0,
                    "cost_value": Decimal("0.00"),
                    "selling_value": Decimal("0.00"),
                }

            branch_breakdown[branch_name]["item_count"] += 1
            branch_breakdown[branch_name]["total_quantity"] += item.quantity
            branch_breakdown[branch_name]["cost_value"] += item.cost_price * item.quantity
            branch_breakdown[branch_name]["selling_value"] += item.selling_price * item.quantity

        return {
            "report_type": "inventory_valuation",
            "generated_at": timezone.now().isoformat(),
            "filters": {
                "branch_id": branch_id,
                "category_id": category_id,
            },
            "summary": {
                "total_items": total_items,
                "total_quantity": total_quantity,
                "total_cost_value": float(total_cost_value),
                "total_selling_value": float(total_selling_value),
                "potential_profit": float(potential_profit),
                "profit_margin_percentage": float(profit_margin),
            },
            "by_category": list(category_breakdown.values()),
            "by_branch": list(branch_breakdown.values()),
        }

    def get_low_stock_alert_report(self, branch_id=None, category_id=None):
        """
        Generate low stock alert report.

        Shows items that are at or below their minimum quantity threshold.

        Args:
            branch_id: Optional branch filter
            category_id: Optional category filter

        Returns:
            dict: Report data with low stock items
        """
        queryset = InventoryItem.objects.filter(
            tenant=self.tenant, is_active=True, quantity__lte=F("min_quantity")
        ).select_related("category", "branch")

        # Apply filters
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Separate out of stock and low stock
        out_of_stock = queryset.filter(quantity=0)
        low_stock = queryset.filter(quantity__gt=0)

        # Build item details
        def build_item_data(item):
            return {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "category": item.category.name,
                "branch": item.branch.name,
                "current_quantity": item.quantity,
                "min_quantity": item.min_quantity,
                "shortage": item.min_quantity - item.quantity,
                "cost_price": float(item.cost_price),
                "selling_price": float(item.selling_price),
                "reorder_value": float(item.cost_price * (item.min_quantity - item.quantity)),
            }

        out_of_stock_items = [build_item_data(item) for item in out_of_stock]
        low_stock_items = [build_item_data(item) for item in low_stock]

        # Calculate reorder costs
        total_reorder_cost = sum(
            item["reorder_value"] for item in out_of_stock_items + low_stock_items
        )

        return {
            "report_type": "low_stock_alert",
            "generated_at": timezone.now().isoformat(),
            "filters": {
                "branch_id": branch_id,
                "category_id": category_id,
            },
            "summary": {
                "total_low_stock_items": len(low_stock_items) + len(out_of_stock_items),
                "out_of_stock_count": len(out_of_stock_items),
                "low_stock_count": len(low_stock_items),
                "total_reorder_cost": float(total_reorder_cost),
            },
            "out_of_stock_items": out_of_stock_items,
            "low_stock_items": low_stock_items,
        }

    def get_dead_stock_analysis_report(self, days_threshold=90, branch_id=None, category_id=None):
        """
        Generate dead stock analysis report.

        Identifies items that haven't moved (sold) in a specified period.
        Note: This is a simplified version. Full implementation would require
        tracking sales history which is implemented in Phase 2 (POS system).

        For now, we identify items based on:
        - Items with quantity > 0 but no recent updates
        - Items that have been in inventory for a long time

        Args:
            days_threshold: Number of days to consider as "dead stock" (default: 90)
            branch_id: Optional branch filter
            category_id: Optional category filter

        Returns:
            dict: Report data with dead stock items
        """
        threshold_date = timezone.now() - timedelta(days=days_threshold)

        queryset = InventoryItem.objects.filter(
            tenant=self.tenant,
            is_active=True,
            quantity__gt=0,
            updated_at__lt=threshold_date,
        ).select_related("category", "branch")

        # Apply filters
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Build item details
        dead_stock_items = []
        total_tied_up_capital = Decimal("0.00")

        for item in queryset:
            days_in_stock = (timezone.now() - item.updated_at).days
            tied_up_capital = item.cost_price * item.quantity

            dead_stock_items.append(
                {
                    "id": str(item.id),
                    "sku": item.sku,
                    "name": item.name,
                    "category": item.category.name,
                    "branch": item.branch.name,
                    "quantity": item.quantity,
                    "cost_price": float(item.cost_price),
                    "selling_price": float(item.selling_price),
                    "tied_up_capital": float(tied_up_capital),
                    "days_in_stock": days_in_stock,
                    "last_updated": item.updated_at.isoformat(),
                }
            )
            total_tied_up_capital += tied_up_capital

        # Sort by tied up capital (highest first)
        dead_stock_items.sort(key=lambda x: x["tied_up_capital"], reverse=True)

        return {
            "report_type": "dead_stock_analysis",
            "generated_at": timezone.now().isoformat(),
            "filters": {
                "days_threshold": days_threshold,
                "branch_id": branch_id,
                "category_id": category_id,
            },
            "summary": {
                "total_dead_stock_items": len(dead_stock_items),
                "total_tied_up_capital": float(total_tied_up_capital),
                "average_days_in_stock": (
                    sum(item["days_in_stock"] for item in dead_stock_items) / len(dead_stock_items)
                    if dead_stock_items
                    else 0
                ),
            },
            "dead_stock_items": dead_stock_items,
        }

    def get_inventory_turnover_report(self, period_days=30, branch_id=None, category_id=None):
        """
        Generate inventory turnover report.

        Shows inventory movement and turnover metrics.
        Note: This is a simplified version. Full implementation would require
        tracking sales history which is implemented in Phase 2 (POS system).

        For now, we provide:
        - Current inventory levels
        - Items by movement frequency (based on update frequency as proxy)
        - Average inventory value

        Args:
            period_days: Period to analyze (default: 30 days)
            branch_id: Optional branch filter
            category_id: Optional category filter

        Returns:
            dict: Report data with turnover metrics
        """
        queryset = InventoryItem.objects.filter(tenant=self.tenant, is_active=True).select_related(
            "category", "branch"
        )

        # Apply filters
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Categorize items by movement
        fast_moving = []  # Updated recently (within period)
        slow_moving = []  # Updated but not recently
        no_movement = []  # Not updated in period

        total_inventory_value = Decimal("0.00")

        for item in queryset:
            inventory_value = item.cost_price * item.quantity
            total_inventory_value += inventory_value

            item_data = {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "category": item.category.name,
                "branch": item.branch.name,
                "quantity": item.quantity,
                "cost_price": float(item.cost_price),
                "selling_price": float(item.selling_price),
                "inventory_value": float(inventory_value),
                "last_updated": item.updated_at.isoformat(),
                "days_since_update": (timezone.now() - item.updated_at).days,
            }

            # Categorize based on update frequency
            days_since_update = (timezone.now() - item.updated_at).days

            if days_since_update <= period_days / 3:  # Updated in first third of period
                fast_moving.append(item_data)
            elif days_since_update <= period_days:  # Updated in period
                slow_moving.append(item_data)
            else:  # Not updated in period
                no_movement.append(item_data)

        # Calculate category-wise turnover
        category_turnover = {}
        for item in queryset:
            cat_name = item.category.name
            if cat_name not in category_turnover:
                category_turnover[cat_name] = {
                    "category": cat_name,
                    "total_items": 0,
                    "total_quantity": 0,
                    "total_value": Decimal("0.00"),
                    "fast_moving_count": 0,
                    "slow_moving_count": 0,
                    "no_movement_count": 0,
                }

            category_turnover[cat_name]["total_items"] += 1
            category_turnover[cat_name]["total_quantity"] += item.quantity
            category_turnover[cat_name]["total_value"] += item.cost_price * item.quantity

            days_since_update = (timezone.now() - item.updated_at).days
            if days_since_update <= period_days / 3:
                category_turnover[cat_name]["fast_moving_count"] += 1
            elif days_since_update <= period_days:
                category_turnover[cat_name]["slow_moving_count"] += 1
            else:
                category_turnover[cat_name]["no_movement_count"] += 1

        # Convert category turnover to list
        category_turnover_list = [
            {
                **data,
                "total_value": float(data["total_value"]),
            }
            for data in category_turnover.values()
        ]

        return {
            "report_type": "inventory_turnover",
            "generated_at": timezone.now().isoformat(),
            "filters": {
                "period_days": period_days,
                "branch_id": branch_id,
                "category_id": category_id,
            },
            "summary": {
                "total_items": queryset.count(),
                "total_inventory_value": float(total_inventory_value),
                "fast_moving_count": len(fast_moving),
                "slow_moving_count": len(slow_moving),
                "no_movement_count": len(no_movement),
                "fast_moving_percentage": (
                    len(fast_moving) / queryset.count() * 100 if queryset.count() > 0 else 0
                ),
            },
            "fast_moving_items": fast_moving[:20],  # Top 20
            "slow_moving_items": slow_moving[:20],  # Top 20
            "no_movement_items": no_movement[:20],  # Top 20
            "by_category": category_turnover_list,
        }
