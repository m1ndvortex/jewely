"""
Branch management views for multi-branch jewelry shops.

Implements Requirement 14: Multi-Branch and Terminal Management
- Branch CRUD operations
- Branch configuration (address, hours, manager assignment)
- Branch performance dashboard with comparative metrics
- Branch-specific inventory tracking
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Avg, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from rest_framework import generics, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.inventory.models import InventoryItem
from apps.sales.models import Sale, Terminal

from .models import Branch, User
from .permissions import TenantPermissionMixin
from .serializers import BranchSerializer, TerminalSerializer


class BranchListView(LoginRequiredMixin, TenantPermissionMixin, ListView):
    """
    List view for branches with search and filtering.
    """

    model = Branch
    template_name = "core/branch_list.html"
    context_object_name = "branches"
    paginate_by = 20

    def get_queryset(self):
        """Filter branches by current tenant and search query."""
        queryset = Branch.objects.filter(tenant=self.request.user.tenant)

        # Search functionality
        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(address__icontains=search)
                | Q(phone__icontains=search)
            )

        # Filter by status
        status_filter = self.request.GET.get("status", "")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.select_related("manager").order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        return context


class BranchDetailView(LoginRequiredMixin, TenantPermissionMixin, DetailView):
    """
    Detail view for a single branch with performance metrics.
    """

    model = Branch
    template_name = "core/branch_detail.html"
    context_object_name = "branch"

    def get_queryset(self):
        return Branch.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch = self.object

        # Calculate date ranges
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)

        # Branch performance metrics
        context.update(self._get_branch_metrics(branch, last_30_days, last_7_days, today))

        # Inventory summary
        context.update(self._get_inventory_summary(branch))

        # Staff summary
        context.update(self._get_staff_summary(branch))

        # Recent activity
        context.update(self._get_recent_activity(branch))

        return context

    def _get_branch_metrics(self, branch, last_30_days, last_7_days, today):
        """Calculate branch performance metrics."""
        # Sales metrics for last 30 days
        sales_30d = Sale.objects.filter(
            branch=branch, status=Sale.COMPLETED, created_at__date__gte=last_30_days
        )

        # Sales metrics for last 7 days
        sales_7d = Sale.objects.filter(
            branch=branch, status=Sale.COMPLETED, created_at__date__gte=last_7_days
        )

        # Today's sales
        sales_today = Sale.objects.filter(
            branch=branch, status=Sale.COMPLETED, created_at__date=today
        )

        return {
            "total_sales_30d": sales_30d.aggregate(total=Sum("total"))["total"] or Decimal("0.00"),
            "sales_count_30d": sales_30d.count(),
            "avg_sale_30d": sales_30d.aggregate(avg=Avg("total"))["avg"] or Decimal("0.00"),
            "total_sales_7d": sales_7d.aggregate(total=Sum("total"))["total"] or Decimal("0.00"),
            "sales_count_7d": sales_7d.count(),
            "total_sales_today": sales_today.aggregate(total=Sum("total"))["total"]
            or Decimal("0.00"),
            "sales_count_today": sales_today.count(),
        }

    def _get_inventory_summary(self, branch):
        """Get inventory summary for the branch."""
        inventory = InventoryItem.objects.filter(branch=branch, is_active=True)

        return {
            "total_items": inventory.count(),
            "total_inventory_value": inventory.aggregate(
                total=Sum(models.F("cost_price") * models.F("quantity"))
            )["total"]
            or Decimal("0.00"),
            "low_stock_items": inventory.filter(quantity__lte=models.F("min_quantity")).count(),
            "out_of_stock_items": inventory.filter(quantity=0).count(),
        }

    def _get_staff_summary(self, branch):
        """Get staff summary for the branch."""
        staff = User.objects.filter(branch=branch, is_active=True)

        return {
            "total_staff": staff.count(),
            "managers": staff.filter(role=User.TENANT_MANAGER).count(),
            "employees": staff.filter(role=User.TENANT_EMPLOYEE).count(),
        }

    def _get_recent_activity(self, branch):
        """Get recent sales activity for the branch."""
        recent_sales = (
            Sale.objects.filter(branch=branch, status=Sale.COMPLETED)
            .select_related("customer", "employee")
            .order_by("-created_at")[:10]
        )

        return {
            "recent_sales": recent_sales,
        }


class BranchCreateView(LoginRequiredMixin, TenantPermissionMixin, CreateView):
    """
    Create view for new branches.
    """

    model = Branch
    template_name = "core/branch_form.html"
    fields = ["name", "address", "phone", "manager", "opening_hours", "is_active"]
    success_url = reverse_lazy("core:branch_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit manager choices to users from the same tenant
        form.fields["manager"].queryset = User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=[User.TENANT_OWNER, User.TENANT_MANAGER],
            is_active=True,
        )
        return form

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant

        # Parse opening hours JSON if provided as string
        opening_hours = form.cleaned_data.get("opening_hours")
        if isinstance(opening_hours, str):
            try:
                form.instance.opening_hours = json.loads(opening_hours)
            except json.JSONDecodeError:
                form.instance.opening_hours = {}

        messages.success(self.request, f'Branch "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class BranchUpdateView(LoginRequiredMixin, TenantPermissionMixin, UpdateView):
    """
    Update view for existing branches.
    """

    model = Branch
    template_name = "core/branch_form.html"
    fields = ["name", "address", "phone", "manager", "opening_hours", "is_active"]
    success_url = reverse_lazy("core:branch_list")

    def get_queryset(self):
        return Branch.objects.filter(tenant=self.request.user.tenant)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit manager choices to users from the same tenant
        form.fields["manager"].queryset = User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=[User.TENANT_OWNER, User.TENANT_MANAGER],
            is_active=True,
        )
        return form

    def form_valid(self, form):
        # Parse opening hours JSON if provided as string
        opening_hours = form.cleaned_data.get("opening_hours")
        if isinstance(opening_hours, str):
            try:
                form.instance.opening_hours = json.loads(opening_hours)
            except json.JSONDecodeError:
                form.instance.opening_hours = {}

        messages.success(self.request, f'Branch "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class BranchDeleteView(LoginRequiredMixin, TenantPermissionMixin, DeleteView):
    """
    Delete view for branches.
    """

    model = Branch
    template_name = "core/branch_confirm_delete.html"
    success_url = reverse_lazy("core:branch_list")

    def get_queryset(self):
        return Branch.objects.filter(tenant=self.request.user.tenant)

    def form_valid(self, form):
        branch = self.get_object()

        # Check if branch has inventory or sales
        has_inventory = InventoryItem.objects.filter(branch=branch).exists()
        has_sales = Sale.objects.filter(branch=branch).exists()
        has_terminals = Terminal.objects.filter(branch=branch).exists()

        if has_inventory or has_sales or has_terminals:
            messages.error(
                self.request,
                f'Cannot delete branch "{branch.name}" because it has associated '
                f"inventory, sales, or terminals. Please transfer or remove them first.",
            )
            return redirect("core:branch_detail", pk=branch.pk)

        messages.success(self.request, f'Branch "{branch.name}" deleted successfully.')
        return super().form_valid(form)


@login_required
def branch_performance_dashboard(request):
    """
    Branch performance dashboard with comparative metrics.
    """
    if not request.user.tenant:
        return redirect("core:home")

    # Get all active branches for the tenant
    branches = Branch.objects.filter(tenant=request.user.tenant, is_active=True).select_related(
        "manager"
    )

    # Calculate date ranges
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)

    # Prepare branch performance data
    branch_data = []
    for branch in branches:
        # Sales metrics for last 30 days
        sales_30d = Sale.objects.filter(
            branch=branch, status=Sale.COMPLETED, created_at__date__gte=last_30_days
        )

        # Inventory metrics
        inventory = InventoryItem.objects.filter(branch=branch, is_active=True)

        branch_metrics = {
            "branch": branch,
            "total_sales_30d": sales_30d.aggregate(total=Sum("total"))["total"] or Decimal("0.00"),
            "sales_count_30d": sales_30d.count(),
            "avg_sale_30d": sales_30d.aggregate(avg=Avg("total"))["avg"] or Decimal("0.00"),
            "inventory_value": inventory.aggregate(
                total=Sum(models.F("cost_price") * models.F("quantity"))
            )["total"]
            or Decimal("0.00"),
            "inventory_count": inventory.count(),
            "low_stock_count": inventory.filter(quantity__lte=models.F("min_quantity")).count(),
            "staff_count": User.objects.filter(branch=branch, is_active=True).count(),
        }
        branch_data.append(branch_metrics)

    # Sort by total sales (descending)
    branch_data.sort(key=lambda x: x["total_sales_30d"], reverse=True)

    # Calculate totals across all branches
    total_metrics = {
        "total_sales": sum(b["total_sales_30d"] for b in branch_data),
        "total_sales_count": sum(b["sales_count_30d"] for b in branch_data),
        "total_inventory_value": sum(b["inventory_value"] for b in branch_data),
        "total_inventory_count": sum(b["inventory_count"] for b in branch_data),
        "total_low_stock": sum(b["low_stock_count"] for b in branch_data),
        "total_staff": sum(b["staff_count"] for b in branch_data),
    }

    # Add percentage calculations
    for branch_metrics in branch_data:
        if total_metrics["total_sales"] > 0:
            branch_metrics["percentage_of_total"] = (
                float(branch_metrics["total_sales_30d"]) / float(total_metrics["total_sales"]) * 100
            )
        else:
            branch_metrics["percentage_of_total"] = 0

    context = {
        "branches": branches,
        "branch_data": branch_data,
        "total_metrics": total_metrics,
        "date_range": f"{last_30_days} to {today}",
    }

    return render(request, "core/branch_performance_dashboard.html", context)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def branch_inventory_api(request, branch_id):
    """
    API endpoint for branch-specific inventory tracking.
    """
    if not request.user.tenant:
        return Response({"error": "User must belong to a tenant"}, status=400)

    try:
        branch = Branch.objects.get(id=branch_id, tenant=request.user.tenant)
    except Branch.DoesNotExist:
        return Response({"error": "Branch not found"}, status=404)

    # Get inventory items for this branch
    inventory = InventoryItem.objects.filter(branch=branch, is_active=True).select_related(
        "category"
    )

    # Apply filters
    category_id = request.GET.get("category")
    if category_id:
        inventory = inventory.filter(category_id=category_id)

    search = request.GET.get("search", "")
    if search:
        inventory = inventory.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    # Low stock filter
    low_stock = request.GET.get("low_stock")
    if low_stock == "true":
        inventory = inventory.filter(quantity__lte=models.F("min_quantity"))

    # Pagination
    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 20))

    paginator = Paginator(inventory, per_page)
    page_obj = paginator.get_page(page)

    # Serialize data
    items_data = []
    for item in page_obj:
        items_data.append(
            {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "category": item.category.name,
                "quantity": item.quantity,
                "min_quantity": item.min_quantity,
                "cost_price": str(item.cost_price),
                "selling_price": str(item.selling_price),
                "is_low_stock": item.is_low_stock(),
                "is_out_of_stock": item.is_out_of_stock(),
            }
        )

    return Response(
        {
            "items": items_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
            "branch": {
                "id": str(branch.id),
                "name": branch.name,
            },
        }
    )


# API Views for REST endpoints


class BranchListCreateAPIView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating branches.
    """

    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.tenant:
            return Branch.objects.none()
        return Branch.objects.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class BranchRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting branches.
    """

    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.tenant:
            return Branch.objects.none()
        return Branch.objects.filter(tenant=self.request.user.tenant)


# Terminal Management Views


class TerminalListView(LoginRequiredMixin, TenantPermissionMixin, ListView):
    """
    List view for terminals with branch filtering.
    """

    model = Terminal
    template_name = "core/terminal_list.html"
    context_object_name = "terminals"
    paginate_by = 20

    def get_queryset(self):
        """Filter terminals by current tenant's branches."""
        branch_ids = Branch.objects.filter(tenant=self.request.user.tenant).values_list(
            "id", flat=True
        )

        queryset = Terminal.objects.filter(branch_id__in=branch_ids)

        # Search functionality
        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(
                Q(terminal_id__icontains=search)
                | Q(description__icontains=search)
                | Q(branch__name__icontains=search)
            )

        # Filter by branch
        branch_filter = self.request.GET.get("branch", "")
        if branch_filter:
            queryset = queryset.filter(branch_id=branch_filter)

        # Filter by status
        status_filter = self.request.GET.get("status", "")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.select_related("branch").order_by("branch__name", "terminal_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "")
        context["branch_filter"] = self.request.GET.get("branch", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["branches"] = Branch.objects.filter(
            tenant=self.request.user.tenant, is_active=True
        ).order_by("name")
        return context


class TerminalCreateView(LoginRequiredMixin, TenantPermissionMixin, CreateView):
    """
    Create view for new terminals.
    """

    model = Terminal
    template_name = "core/terminal_form.html"
    fields = ["terminal_id", "description", "branch", "configuration", "is_active"]
    success_url = reverse_lazy("core:terminal_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit branch choices to branches from the same tenant
        form.fields["branch"].queryset = Branch.objects.filter(
            tenant=self.request.user.tenant, is_active=True
        )
        return form

    def form_valid(self, form):
        # Parse configuration JSON if provided as string
        configuration = form.cleaned_data.get("configuration")
        if isinstance(configuration, str):
            try:
                form.instance.configuration = json.loads(configuration)
            except json.JSONDecodeError:
                form.instance.configuration = {}

        messages.success(
            self.request, f'Terminal "{form.instance.terminal_id}" created successfully.'
        )
        return super().form_valid(form)


class TerminalUpdateView(LoginRequiredMixin, TenantPermissionMixin, UpdateView):
    """
    Update view for existing terminals.
    """

    model = Terminal
    template_name = "core/terminal_form.html"
    fields = ["terminal_id", "description", "branch", "configuration", "is_active"]
    success_url = reverse_lazy("core:terminal_list")

    def get_queryset(self):
        branch_ids = Branch.objects.filter(tenant=self.request.user.tenant).values_list(
            "id", flat=True
        )
        return Terminal.objects.filter(branch_id__in=branch_ids)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit branch choices to branches from the same tenant
        form.fields["branch"].queryset = Branch.objects.filter(
            tenant=self.request.user.tenant, is_active=True
        )
        return form

    def form_valid(self, form):
        # Parse configuration JSON if provided as string
        configuration = form.cleaned_data.get("configuration")
        if isinstance(configuration, str):
            try:
                form.instance.configuration = json.loads(configuration)
            except json.JSONDecodeError:
                form.instance.configuration = {}

        messages.success(
            self.request, f'Terminal "{form.instance.terminal_id}" updated successfully.'
        )
        return super().form_valid(form)


class TerminalDeleteView(LoginRequiredMixin, TenantPermissionMixin, DeleteView):
    """
    Delete view for terminals.
    """

    model = Terminal
    template_name = "core/terminal_confirm_delete.html"
    success_url = reverse_lazy("core:terminal_list")

    def get_queryset(self):
        branch_ids = Branch.objects.filter(tenant=self.request.user.tenant).values_list(
            "id", flat=True
        )
        return Terminal.objects.filter(branch_id__in=branch_ids)

    def delete(self, request, *args, **kwargs):
        terminal = self.get_object()

        # Check if terminal has sales
        has_sales = Sale.objects.filter(terminal=terminal).exists()

        if has_sales:
            messages.error(
                request,
                f'Cannot delete terminal "{terminal.terminal_id}" because it has associated '
                f"sales records. Please archive it instead by marking it as inactive.",
            )
            return redirect("core:terminal_list")

        messages.success(request, f'Terminal "{terminal.terminal_id}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


# Staff Assignment Views


@login_required
def staff_assignment_view(request):
    """
    View for managing staff assignments to branches.
    """
    if not request.user.tenant:
        return redirect("core:home")

    # Get all staff for the tenant
    staff = (
        User.objects.filter(tenant=request.user.tenant, is_active=True)
        .select_related("branch")
        .order_by("role", "username")
    )

    # Get all branches for the tenant
    branches = Branch.objects.filter(tenant=request.user.tenant, is_active=True).order_by("name")

    context = {
        "staff": staff,
        "branches": branches,
    }

    return render(request, "core/staff_assignment.html", context)


def _validate_assignment_data(request_data):
    """Validate user_id and branch_id formats."""
    user_id = request_data.get("user_id")
    branch_id = request_data.get("branch_id")

    if not user_id:
        return None, None, Response({"error": "user_id is required"}, status=400)

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None, None, Response({"error": "Invalid user_id format"}, status=400)

    if branch_id:
        try:
            from uuid import UUID

            UUID(branch_id)
        except (ValueError, TypeError):
            return None, None, Response({"error": "Invalid branch_id format"}, status=400)

    return user_id, branch_id, None


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def assign_staff_to_branch(request):
    """API endpoint for assigning staff to branches."""
    if not request.user.tenant:
        return Response({"error": "User must belong to a tenant"}, status=400)

    user_id, branch_id, error_response = _validate_assignment_data(request.data)
    if error_response:
        return error_response

    try:
        user = User.objects.get(id=user_id, tenant=request.user.tenant)
        branch = None
        if branch_id:
            branch = Branch.objects.get(id=branch_id, tenant=request.user.tenant)

        user.branch = branch
        user.save(update_fields=["branch"])

        return Response(
            {
                "success": True,
                "message": f'User {user.username} assigned to {branch.name if branch else "no branch"}',
                "user_id": str(user.id),
                "branch_id": str(branch.id) if branch else None,
                "branch_name": branch.name if branch else None,
            }
        )

    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    except Branch.DoesNotExist:
        return Response({"error": "Branch not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# Terminal API Views


class TerminalListCreateAPIView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating terminals.
    """

    serializer_class = TerminalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.tenant:
            return Terminal.objects.none()

        branch_ids = Branch.objects.filter(tenant=self.request.user.tenant).values_list(
            "id", flat=True
        )

        return Terminal.objects.filter(branch_id__in=branch_ids)

    def perform_create(self, serializer):
        # Ensure the branch belongs to the user's tenant
        branch = serializer.validated_data["branch"]
        if branch.tenant != self.request.user.tenant:
            raise serializers.ValidationError("Branch must belong to your tenant")

        serializer.save()


class TerminalRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, and deleting terminals.
    """

    serializer_class = TerminalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.tenant:
            return Terminal.objects.none()

        branch_ids = Branch.objects.filter(tenant=self.request.user.tenant).values_list(
            "id", flat=True
        )

        return Terminal.objects.filter(branch_id__in=branch_ids)
