"""
Views for sales and POS functionality.

Implements Requirement 11: Point of Sale (POS) System
- POS interface for processing in-store sales
- Product search with barcode scanner support
- Cart management
- Customer selection/quick add
- Payment method selection
- Receipt generation
"""

from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import HasTenantAccess
from apps.core.tenant_context import set_tenant_context
from apps.inventory.models import InventoryItem

from .models import Customer, Sale, Terminal
from .serializers import (
    CustomerListSerializer,
    CustomerQuickAddSerializer,
    SaleCreateSerializer,
    SaleDetailSerializer,
    SaleHoldSerializer,
    SaleListSerializer,
    TerminalListSerializer,
)


class TenantContextMixin:
    """Mixin to set tenant context for API views."""

    def initial(self, request, *args, **kwargs):
        """Set tenant context after authentication."""
        super().initial(request, *args, **kwargs)
        if hasattr(request, "user") and hasattr(request.user, "tenant") and request.user.tenant:
            set_tenant_context(request.user.tenant.id)


# POS Interface Views


@require_http_methods(["GET"])
def pos_interface(request):
    """
    Main POS interface view.

    Renders the POS interface with:
    - Product search section
    - Cart section
    - Checkout section
    - Customer selection
    - Payment method selection

    Implements Requirement 11: Fast and intuitive POS interface
    """
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect("/accounts/login/")

    # Get user's active terminals
    terminals = Terminal.objects.filter(
        branch__tenant=request.user.tenant, is_active=True
    ).select_related("branch")

    context = {
        "user": request.user,
        "terminals": terminals,
    }

    return render(request, "sales/pos_interface.html", context)


# API Endpoints for POS


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_product_search(request):
    """
    Search products for POS with barcode scanner support.

    Query parameters:
    - q: Search query (SKU, name, barcode, serial number)
    - branch: Optional branch filter
    - category: Optional category filter
    - limit: Number of results (default: 20)

    Implements Requirement 11.2: Product search with barcode scanner support
    Implements Requirement 35.6: Barcode scanning for quick item lookup
    """
    tenant = request.user.tenant
    query = request.query_params.get("q", "").strip()
    branch_id = request.query_params.get("branch")
    category_id = request.query_params.get("category")
    limit = int(request.query_params.get("limit", "20"))

    if not query:
        return Response({"results": []}, status=status.HTTP_200_OK)

    # Build queryset
    queryset = InventoryItem.objects.filter(
        tenant=tenant, is_active=True, quantity__gt=0
    ).select_related("category", "branch")

    # Search by SKU, name, barcode, serial number
    queryset = queryset.filter(
        Q(sku__icontains=query)
        | Q(name__icontains=query)
        | Q(barcode__iexact=query)  # Exact match for barcode
        | Q(serial_number__iexact=query)  # Exact match for serial
        | Q(description__icontains=query)
    )

    # Apply filters
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    # Limit results
    queryset = queryset[:limit]

    # Serialize results
    results = []
    for item in queryset:
        results.append(
            {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "category": item.category.name if item.category else None,
                "karat": item.karat,
                "weight_grams": str(item.weight_grams),
                "selling_price": str(item.selling_price),
                "quantity": item.quantity,
                "branch": item.branch.name,
                "barcode": item.barcode,
                "serial_number": item.serial_number,
            }
        )

    return Response({"results": results}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_customer_search(request):
    """
    Search customers for POS.

    Query parameters:
    - q: Search query (name, phone, email, customer number)
    - limit: Number of results (default: 10)

    Implements Requirement 11: Customer selection during checkout
    """
    tenant = request.user.tenant
    query = request.query_params.get("q", "").strip()
    limit = int(request.query_params.get("limit", "10"))

    if not query:
        return Response({"results": []}, status=status.HTTP_200_OK)

    # Search customers
    queryset = Customer.objects.filter(tenant=tenant).filter(
        Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(phone__icontains=query)
        | Q(email__icontains=query)
        | Q(customer_number__icontains=query)
    )[:limit]

    serializer = CustomerListSerializer(queryset, many=True)
    return Response({"results": serializer.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_customer_quick_add(request):
    """
    Quick add customer during POS checkout.

    Only requires essential fields:
    - first_name
    - last_name
    - phone

    Implements Requirement 11: Customer quick add during checkout
    """
    serializer = CustomerQuickAddSerializer(data=request.data, context={"request": request})

    if serializer.is_valid():
        customer = serializer.save()
        return Response(
            CustomerListSerializer(customer).data,
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_terminals(request):
    """
    Get active terminals for current user's branch.

    Implements Requirement 14: Terminal management
    """
    tenant = request.user.tenant

    # Get terminals for user's branch or all if user has access
    if request.user.branch:
        terminals = Terminal.objects.filter(
            branch=request.user.branch, is_active=True
        ).select_related("branch")
    else:
        terminals = Terminal.objects.filter(branch__tenant=tenant, is_active=True).select_related(
            "branch"
        )

    serializer = TerminalListSerializer(terminals, many=True)
    return Response({"terminals": serializer.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_create_sale(request):
    """
    Create a new sale through POS.

    Request body:
    {
        "customer_id": "uuid" (optional),
        "terminal_id": "uuid",
        "items": [
            {
                "inventory_item_id": "uuid",
                "quantity": 1,
                "unit_price": "100.00" (optional, uses current price if not provided),
                "discount": "0.00" (optional)
            }
        ],
        "payment_method": "CASH|CARD|STORE_CREDIT|SPLIT|OTHER",
        "payment_details": {} (optional),
        "tax_rate": "10.00" (optional, percentage),
        "discount": "0.00" (optional),
        "notes": "" (optional),
        "status": "COMPLETED|ON_HOLD" (optional, default: COMPLETED)
    }

    Implements Requirement 11: Complete sale processing
    - Multiple payment methods
    - Automatic inventory deduction
    - Tax and discount calculation
    """
    set_tenant_context(request.user.tenant.id)

    serializer = SaleCreateSerializer(data=request.data, context={"request": request})

    if serializer.is_valid():
        try:
            sale = serializer.save()
            return Response(
                SaleDetailSerializer(sale).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_hold_sale(request, sale_id):
    """
    Put a sale on hold to resume later.

    Implements Requirement 11.11: Allow transactions to be put on hold and resumed later
    Implements Requirement 35.12: Allow transactions to be put on hold and resumed later
    """
    try:
        sale = Sale.objects.get(id=sale_id, tenant=request.user.tenant)
    except Sale.DoesNotExist:
        return Response(
            {"detail": "Sale not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = SaleHoldSerializer(sale, data=request.data)

    if serializer.is_valid():
        sale = serializer.save()
        return Response(
            SaleDetailSerializer(sale).data,
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_held_sales(request):
    """
    Get all sales on hold for current terminal/branch.

    Implements Requirement 11.11: Resume held transactions
    """
    tenant = request.user.tenant

    # Get held sales for user's branch
    if request.user.branch:
        held_sales = Sale.objects.filter(
            tenant=tenant, branch=request.user.branch, status=Sale.ON_HOLD
        ).order_by("-created_at")
    else:
        held_sales = Sale.objects.filter(tenant=tenant, status=Sale.ON_HOLD).order_by("-created_at")

    serializer = SaleListSerializer(held_sales, many=True)
    return Response({"held_sales": serializer.data}, status=status.HTTP_200_OK)


# Sale Management Views


class SaleListView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for listing sales with filters.

    Query parameters:
    - search: Search by sale number, customer name
    - branch: Filter by branch
    - employee: Filter by employee
    - terminal: Filter by terminal
    - payment_method: Filter by payment method
    - status: Filter by status
    - date_from: Filter by date (YYYY-MM-DD)
    - date_to: Filter by date (YYYY-MM-DD)
    """

    serializer_class = SaleListSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "total", "sale_number"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get sales for current user's tenant with filters."""
        user = self.request.user
        queryset = Sale.objects.filter(tenant=user.tenant).select_related(
            "customer", "branch", "terminal", "employee"
        )

        # Search
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(sale_number__icontains=search)
                | Q(customer__first_name__icontains=search)
                | Q(customer__last_name__icontains=search)
            )

        # Filters
        branch_id = self.request.query_params.get("branch")
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        employee_id = self.request.query_params.get("employee")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        terminal_id = self.request.query_params.get("terminal")
        if terminal_id:
            queryset = queryset.filter(terminal_id=terminal_id)

        payment_method = self.request.query_params.get("payment_method")
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        sale_status = self.request.query_params.get("status")
        if sale_status:
            queryset = queryset.filter(status=sale_status)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset


class SaleDetailView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single sale.
    """

    serializer_class = SaleDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get sales for current user's tenant."""
        user = self.request.user
        return (
            Sale.objects.filter(tenant=user.tenant)
            .select_related("customer", "branch", "terminal", "employee")
            .prefetch_related("items__inventory_item")
        )


# Customer Management Views


class CustomerListView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for listing customers.
    """

    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["first_name", "last_name", "created_at", "total_purchases"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get customers for current user's tenant."""
        user = self.request.user
        queryset = Customer.objects.filter(tenant=user.tenant)

        # Search
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
                | Q(customer_number__icontains=search)
            )

        # Filter by loyalty tier
        tier = self.request.query_params.get("tier")
        if tier:
            queryset = queryset.filter(loyalty_tier=tier)

        return queryset
