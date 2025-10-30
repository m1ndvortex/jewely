"""
Web views for inventory management.

Provides full-featured web interface for inventory operations including:
- List view with advanced search and filters
- Detail view with complete item information
- Create/Edit forms with validation
- Stock adjustment interface
- Barcode/QR code generation
- Inventory reports
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.decorators import tenant_required
from apps.core.mixins import TenantRequiredMixin
from apps.core.tenant_context import tenant_context

from .forms import InventoryItemForm, ProductCategoryForm, StockAdjustmentForm
from .models import InventoryItem, InventoryTransfer, ProductCategory


class InventoryListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """
    Comprehensive inventory list view with search, filters, and pagination.

    Features:
    - Advanced search across multiple fields
    - Category, branch, karat, status filters
    - Low stock and out of stock alerts
    - Sortable columns
    - Bulk actions support
    - Export functionality
    """

    model = InventoryItem
    template_name = "inventory/inventory_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        """Get filtered and searched inventory items."""
        user = self.request.user

        with tenant_context(user.tenant.id):
            queryset = (
                InventoryItem.objects.filter(tenant=user.tenant)
                .select_related("category", "branch", "tenant")
                .order_by("-created_at")
            )

            # Search functionality
            search = self.request.GET.get("search", "").strip()
            if search:
                queryset = queryset.filter(
                    Q(sku__icontains=search)
                    | Q(name__icontains=search)
                    | Q(serial_number__icontains=search)
                    | Q(lot_number__icontains=search)
                    | Q(barcode__icontains=search)
                    | Q(description__icontains=search)
                )

            # Category filter
            category_id = self.request.GET.get("category")
            if category_id:
                queryset = queryset.filter(category_id=category_id)

            # Branch filter
            branch_id = self.request.GET.get("branch")
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)

            # Karat filter
            karat = self.request.GET.get("karat")
            if karat:
                queryset = queryset.filter(karat=karat)

            # Status filter
            status_filter = self.request.GET.get("status")
            if status_filter == "active":
                queryset = queryset.filter(is_active=True)
            elif status_filter == "inactive":
                queryset = queryset.filter(is_active=False)
            elif status_filter == "low_stock":
                queryset = queryset.filter(quantity__lte=F("min_quantity"), quantity__gt=0)
            elif status_filter == "out_of_stock":
                queryset = queryset.filter(quantity=0)

            # Sorting
            sort_by = self.request.GET.get("sort", "-created_at")
            if sort_by:
                queryset = queryset.order_by(sort_by)

            return queryset

    def get_context_data(self, **kwargs):
        """Add additional context for filters and statistics."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        with tenant_context(user.tenant.id):
            # Get categories for filter dropdown
            context["categories"] = ProductCategory.objects.filter(tenant=user.tenant).order_by(
                "name"
            )

            # Get branches for filter dropdown
            from apps.core.models import Branch

            context["branches"] = Branch.objects.filter(tenant=user.tenant).order_by("name")

            # Calculate statistics
            all_items = InventoryItem.objects.filter(tenant=user.tenant)
            context["stats"] = {
                "total_items": all_items.count(),
                "total_quantity": all_items.aggregate(Sum("quantity"))["quantity__sum"] or 0,
                "total_value": sum(item.quantity * item.cost_price for item in all_items),
                "low_stock_count": all_items.filter(
                    quantity__lte=F("min_quantity"), quantity__gt=0
                ).count(),
                "out_of_stock_count": all_items.filter(quantity=0).count(),
            }

            # Preserve filter parameters
            context["current_filters"] = {
                "search": self.request.GET.get("search", ""),
                "category": self.request.GET.get("category", ""),
                "branch": self.request.GET.get("branch", ""),
                "karat": self.request.GET.get("karat", ""),
                "status": self.request.GET.get("status", ""),
                "sort": self.request.GET.get("sort", "-created_at"),
            }

            # Karat options
            context["karat_options"] = [
                ("24K", "24K"),
                ("22K", "22K"),
                ("21K", "21K"),
                ("18K", "18K"),
                ("14K", "14K"),
                ("10K", "10K"),
            ]

        return context


class InventoryDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """
    Detailed view of a single inventory item.

    Shows:
    - Complete item information
    - Stock history
    - Transfer history
    - Sales history
    - Barcode/QR code
    - Related items
    """

    model = InventoryItem
    template_name = "inventory/inventory_detail.html"
    context_object_name = "item"
    pk_url_kwarg = "id"

    def get_queryset(self):
        """Ensure user can only access their tenant's items."""
        return InventoryItem.objects.filter(tenant=self.request.user.tenant).select_related(
            "category", "branch", "tenant"
        )

    def get_context_data(self, **kwargs):
        """Add related data to context."""
        context = super().get_context_data(**kwargs)
        item = self.object

        with tenant_context(self.request.user.tenant.id):
            # Get stock adjustment history (if model exists)
            # context['stock_history'] = item.stock_adjustments.all()[:10]

            # Get transfer history
            context["transfers"] = (
                InventoryTransfer.objects.filter(
                    Q(from_branch=item.branch) | Q(to_branch=item.branch)
                )
                .select_related("from_branch", "to_branch", "requested_by")
                .order_by("-created_at")[:10]
            )

            # Get sales history (if available)
            from apps.sales.models import SaleItem

            context["sales"] = (
                SaleItem.objects.filter(inventory_item=item)
                .select_related("sale", "sale__customer")
                .order_by("-sale__created_at")[:10]
            )

            # Calculate metrics
            context["metrics"] = {
                "stock_value": item.quantity * item.cost_price,
                "potential_profit": item.quantity * (item.selling_price - item.cost_price),
                "margin_percentage": (
                    ((item.selling_price - item.cost_price) / item.cost_price * 100)
                    if item.cost_price > 0
                    else 0
                ),
                "days_in_stock": (item.updated_at - item.created_at).days if item.updated_at else 0,
            }

        return context


class InventoryCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """
    Create new inventory item with comprehensive form validation.
    """

    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/inventory_form.html"
    success_url = reverse_lazy("inventory:inventory_list")

    def get_form_kwargs(self):
        """Pass tenant to form."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def form_valid(self, form):
        """Set tenant before saving."""
        form.instance.tenant = self.request.user.tenant
        messages.success(
            self.request, _('Inventory item "{}" created successfully.').format(form.instance.name)
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context for form."""
        context = super().get_context_data(**kwargs)
        context["title"] = _("Add New Inventory Item")
        context["submit_text"] = _("Create Item")
        return context


class InventoryUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """
    Update existing inventory item.
    """

    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/inventory_form.html"
    pk_url_kwarg = "id"

    def get_queryset(self):
        """Ensure user can only edit their tenant's items."""
        return InventoryItem.objects.filter(tenant=self.request.user.tenant)

    def get_form_kwargs(self):
        """Pass tenant to form."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_success_url(self):
        """Redirect to detail view after update."""
        return reverse("inventory:inventory_detail", kwargs={"id": self.object.id})

    def form_valid(self, form):
        """Show success message."""
        messages.success(
            self.request, _('Inventory item "{}" updated successfully.').format(form.instance.name)
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Add context for form."""
        context = super().get_context_data(**kwargs)
        context["title"] = _("Edit Inventory Item")
        context["submit_text"] = _("Update Item")
        return context


class InventoryDeleteView(LoginRequiredMixin, TenantRequiredMixin, DeleteView):
    """
    Delete inventory item with confirmation.
    """

    model = InventoryItem
    template_name = "inventory/inventory_confirm_delete.html"
    success_url = reverse_lazy("inventory:inventory_list")
    pk_url_kwarg = "id"

    def get_queryset(self):
        """Ensure user can only delete their tenant's items."""
        return InventoryItem.objects.filter(tenant=self.request.user.tenant)

    def delete(self, request, *args, **kwargs):
        """Show success message after deletion."""
        item = self.get_object()
        messages.success(request, _('Inventory item "{}" deleted successfully.').format(item.name))
        return super().delete(request, *args, **kwargs)


@login_required
@tenant_required
@require_http_methods(["GET", "POST"])
def stock_adjustment_view(request, id):
    """
    Adjust stock levels for an inventory item.

    Supports:
    - Increase/decrease quantity
    - Reason tracking
    - Audit trail
    """
    item = get_object_or_404(InventoryItem, id=id, tenant=request.user.tenant)

    if request.method == "POST":
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            adjustment_type = form.cleaned_data["adjustment_type"]
            quantity = form.cleaned_data["quantity"]
            # reason = form.cleaned_data["reason"]  # TODO: Add audit logging
            # notes = form.cleaned_data.get("notes", "")  # TODO: Add audit logging

            with tenant_context(request.user.tenant.id):
                # Update quantity
                if adjustment_type == "increase":
                    item.quantity += quantity
                else:
                    if item.quantity < quantity:
                        messages.error(request, _("Cannot decrease quantity below zero."))
                        return render(
                            request, "inventory/stock_adjustment.html", {"item": item, "form": form}
                        )
                    item.quantity -= quantity

                item.save()

                # Log adjustment (if audit model exists)
                # StockAdjustment.objects.create(...)

                messages.success(
                    request,
                    _("Stock adjusted successfully. New quantity: {}").format(item.quantity),
                )
                return redirect("inventory:inventory_detail", id=item.id)
    else:
        form = StockAdjustmentForm()

    return render(request, "inventory/stock_adjustment.html", {"item": item, "form": form})


@login_required
@tenant_required
def generate_barcode_view(request, id):
    """Generate and display barcode for inventory item."""
    item = get_object_or_404(InventoryItem, id=id, tenant=request.user.tenant)

    # Import barcode generation
    from .barcode_utils import generate_barcode_image

    barcode_data = generate_barcode_image(item.barcode or item.sku)

    return HttpResponse(barcode_data, content_type="image/png")


@login_required
@tenant_required
def generate_qr_code_view(request, id):
    """Generate and display QR code for inventory item."""
    item = get_object_or_404(InventoryItem, id=id, tenant=request.user.tenant)

    # Import QR code generation
    from .barcode_utils import generate_qr_code_image

    # Create QR data with item details
    qr_data = {
        "sku": item.sku,
        "name": item.name,
        "price": str(item.selling_price),
        "url": request.build_absolute_uri(
            reverse("inventory:inventory_detail", kwargs={"id": item.id})
        ),
    }

    import json

    qr_image = generate_qr_code_image(json.dumps(qr_data))

    return HttpResponse(qr_image, content_type="image/png")


@login_required
@tenant_required
def print_label_view(request, id):
    """Generate printable label with barcode/QR code."""
    item = get_object_or_404(InventoryItem, id=id, tenant=request.user.tenant)

    return render(request, "inventory/print_label.html", {"item": item})


@login_required
@tenant_required
def inventory_reports_view(request):
    """
    Inventory reports dashboard.

    Provides access to:
    - Valuation report
    - Low stock alert
    - Dead stock analysis
    - Turnover report
    """
    user = request.user

    with tenant_context(user.tenant.id):
        items = InventoryItem.objects.filter(tenant=user.tenant)

        # Calculate report data
        total_value = sum(item.quantity * item.cost_price for item in items)
        low_stock_items = items.filter(quantity__lte=F("reorder_level"), quantity__gt=0).count()
        out_of_stock_items = items.filter(quantity=0).count()

        # Dead stock (items not sold in 90 days)
        # TODO: Add dead stock analysis
        # from datetime import timedelta
        # from django.utils import timezone
        # ninety_days_ago = timezone.now() - timedelta(days=90)

        context = {
            "total_items": items.count(),
            "total_value": total_value,
            "low_stock_count": low_stock_items,
            "out_of_stock_count": out_of_stock_items,
            "low_stock_items": items.filter(quantity__lte=F("reorder_level"), quantity__gt=0)[:20],
            "out_of_stock_items": items.filter(quantity=0)[:20],
        }

    return render(request, "inventory/reports.html", context)


@login_required
@tenant_required
def category_list_view(request):
    """List all product categories with hierarchical display."""
    user = request.user

    with tenant_context(user.tenant.id):
        all_categories = ProductCategory.objects.filter(tenant=user.tenant)

        # Search functionality
        search = request.GET.get("search", "")
        if search:
            categories = (
                all_categories.filter(Q(name__icontains=search) | Q(description__icontains=search))
                .annotate(item_count=Count("items"))
                .order_by("display_order", "name")
            )
        else:
            # Show all categories
            categories = all_categories.annotate(item_count=Count("items")).order_by(
                "display_order", "name"
            )

        # Statistics
        stats = {
            "total_categories": all_categories.count(),
            "active_categories": all_categories.filter(is_active=True).count(),
            "top_level_categories": all_categories.filter(parent__isnull=True).count(),
        }

    return render(
        request,
        "inventory/category_list.html",
        {"categories": categories, "stats": stats, "search": search},
    )


@login_required
@tenant_required
@require_http_methods(["GET", "POST"])
def category_create_view(request):
    """Create new product category."""
    if request.method == "POST":
        form = ProductCategoryForm(request.POST, request.FILES, tenant=request.user.tenant)
        if form.is_valid():
            category = form.save(commit=False)
            category.tenant = request.user.tenant
            category.save()
            messages.success(
                request, _('Category "{}" created successfully.').format(category.name)
            )
            return redirect("inventory:category_list")
    else:
        # Pre-select parent if provided in URL
        parent_id = request.GET.get("parent")
        initial = {}
        if parent_id:
            try:
                parent = ProductCategory.objects.get(id=parent_id, tenant=request.user.tenant)
                initial["parent"] = parent
            except ProductCategory.DoesNotExist:
                pass

        form = ProductCategoryForm(tenant=request.user.tenant, initial=initial)

    return render(
        request,
        "inventory/category_form.html",
        {"form": form, "title": _("Add New Category"), "is_edit": False},
    )


@login_required
@tenant_required
@require_http_methods(["GET", "POST"])
def category_edit_view(request, id):
    """Edit existing product category."""
    category = get_object_or_404(ProductCategory, id=id, tenant=request.user.tenant)

    if request.method == "POST":
        form = ProductCategoryForm(
            request.POST, request.FILES, instance=category, tenant=request.user.tenant
        )
        if form.is_valid():
            form.save()
            messages.success(
                request, _('Category "{}" updated successfully.').format(category.name)
            )
            return redirect("inventory:category_list")
    else:
        form = ProductCategoryForm(instance=category, tenant=request.user.tenant)

    return render(
        request,
        "inventory/category_form.html",
        {"form": form, "category": category, "title": _("Edit Category"), "is_edit": True},
    )


@login_required
@tenant_required
@require_http_methods(["GET", "POST"])
def category_delete_view(request, id):
    """Delete a product category."""
    category = get_object_or_404(ProductCategory, id=id, tenant=request.user.tenant)

    # Check if category has items
    item_count = category.items.count()
    has_subcategories = category.subcategories.exists()

    if request.method == "POST":
        if item_count > 0:
            messages.error(
                request,
                _(
                    'Cannot delete category "{}". It has {} items. Please move or delete the items first.'
                ).format(category.name, item_count),
            )
        elif has_subcategories:
            messages.error(
                request,
                _(
                    'Cannot delete category "{}". It has subcategories. Please delete subcategories first.'
                ).format(category.name),
            )
        else:
            category_name = category.name
            category.delete()
            messages.success(
                request, _('Category "{}" deleted successfully.').format(category_name)
            )
            return redirect("inventory:category_list")

    return render(
        request,
        "inventory/category_delete.html",
        {"category": category, "item_count": item_count, "has_subcategories": has_subcategories},
    )


@login_required
@tenant_required
def category_detail_view(request, id):
    """View category details with items and subcategories."""
    category = get_object_or_404(ProductCategory, id=id, tenant=request.user.tenant)

    # Get items in this category
    items = category.items.filter(is_active=True).order_by("-created_at")[:20]

    # Get subcategories
    subcategories = category.get_children()

    # Statistics
    total_items = category.get_item_count()
    total_value = sum(item.calculate_total_selling_value() for item in category.items.all())

    context = {
        "category": category,
        "items": items,
        "subcategories": subcategories,
        "total_items": total_items,
        "total_value": total_value,
    }

    return render(request, "inventory/category_detail.html", context)
