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
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import HasTenantAccess
from apps.core.tenant_context import set_tenant_context
from apps.inventory.models import InventoryItem

from .models import Customer, Sale, Terminal
from .receipt_service import ReceiptService
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
    Create a new sale through POS with enhanced backend logic.

    Request body:
    {
        "customer_id": "uuid" (optional),
        "terminal_id": "uuid",
        "items": [
            {
                "inventory_item_id": "uuid",
                "quantity": 1,
                "unit_price": "100.00" (optional, uses current price if not provided),
                "discount": "0.00" (optional, item-level discount)
            }
        ],
        "payment_method": "CASH|CARD|STORE_CREDIT|SPLIT|OTHER",
        "payment_details": {} (optional),
        "tax_rate": "10.00" (optional, percentage),
        "discount_type": "FIXED|PERCENTAGE" (optional, default: FIXED),
        "discount_value": "0.00" (optional, sale-level discount),
        "notes": "" (optional),
        "status": "COMPLETED|ON_HOLD" (optional, default: COMPLETED)
    }

    Implements Requirement 11: Complete POS backend logic
    - Transaction handling with atomic operations
    - Inventory deduction with select_for_update locking
    - Inventory availability validation before sale
    - Tax and discount calculation (both fixed and percentage)
    - Unique sale number generation with collision handling
    - Multiple payment methods support
    - Automatic inventory deduction
    - Customer purchase tracking
    - Terminal usage tracking
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
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"POS sale creation failed: {str(e)}", exc_info=True)

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


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_validate_inventory(request):
    """
    Validate inventory availability for POS sale before processing.

    This endpoint allows the frontend to check inventory availability
    without creating a sale, providing better user experience.

    Request body:
    {
        "items": [
            {
                "inventory_item_id": "uuid",
                "quantity": 1
            }
        ]
    }

    Response:
    {
        "valid": true/false,
        "items": [
            {
                "inventory_item_id": "uuid",
                "available": true/false,
                "available_quantity": 10,
                "requested_quantity": 2,
                "error": "error message if any"
            }
        ]
    }

    Implements Requirement 11: Inventory availability validation
    """
    tenant = request.user.tenant
    items_data = request.data.get("items", [])

    if not items_data:
        return Response({"detail": "Items list is required."}, status=status.HTTP_400_BAD_REQUEST)

    validation_results = []
    all_valid = True

    for item_data in items_data:
        inventory_item_id = item_data.get("inventory_item_id")
        requested_quantity = item_data.get("quantity", 1)

        result = {
            "inventory_item_id": inventory_item_id,
            "requested_quantity": requested_quantity,
            "available": False,
            "available_quantity": 0,
            "error": None,
        }

        try:
            inventory_item = InventoryItem.objects.get(
                id=inventory_item_id, tenant=tenant, is_active=True
            )

            result["available_quantity"] = inventory_item.quantity

            # Check availability
            if inventory_item.quantity >= requested_quantity:
                result["available"] = True
            else:
                result["available"] = False
                result["error"] = f"Insufficient inventory. Available: {inventory_item.quantity}"
                all_valid = False

            # Check serialized items
            if inventory_item.serial_number and requested_quantity > 1:
                result["available"] = False
                result["error"] = "Cannot sell more than 1 unit of serialized item"
                all_valid = False

        except InventoryItem.DoesNotExist:
            result["error"] = "Inventory item not found or inactive"
            all_valid = False

        validation_results.append(result)

    return Response({"valid": all_valid, "items": validation_results}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_calculate_totals(request):
    """
    Calculate sale totals without creating a sale.

    This endpoint allows the frontend to show live total calculations
    as the user builds their cart.

    Request body:
    {
        "items": [
            {
                "inventory_item_id": "uuid",
                "quantity": 1,
                "unit_price": "100.00" (optional),
                "discount": "0.00" (optional)
            }
        ],
        "tax_rate": "10.00" (optional, percentage),
        "discount_type": "FIXED|PERCENTAGE" (optional),
        "discount_value": "0.00" (optional)
    }

    Response:
    {
        "subtotal": "100.00",
        "discount_amount": "10.00",
        "tax_amount": "9.00",
        "total": "99.00",
        "items": [
            {
                "inventory_item_id": "uuid",
                "quantity": 1,
                "unit_price": "100.00",
                "subtotal": "100.00"
            }
        ]
    }

    Implements Requirement 11: Tax and discount calculation
    """
    from decimal import Decimal

    tenant = request.user.tenant
    items_data = request.data.get("items", [])
    tax_rate = Decimal(str(request.data.get("tax_rate", "0.00")))
    discount_type = request.data.get("discount_type", "FIXED")
    discount_value = Decimal(str(request.data.get("discount_value", "0.00")))

    if not items_data:
        return Response({"detail": "Items list is required."}, status=status.HTTP_400_BAD_REQUEST)

    subtotal = Decimal("0.00")
    calculated_items = []

    try:
        for item_data in items_data:
            inventory_item_id = item_data.get("inventory_item_id")
            quantity = int(item_data.get("quantity", 1))

            # Get inventory item
            inventory_item = InventoryItem.objects.get(
                id=inventory_item_id, tenant=tenant, is_active=True
            )

            # Use provided unit price or current selling price
            unit_price = Decimal(str(item_data.get("unit_price", inventory_item.selling_price)))
            item_discount = Decimal(str(item_data.get("discount", "0.00")))

            item_subtotal = (unit_price * quantity) - item_discount
            subtotal += item_subtotal

            calculated_items.append(
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                    "discount": str(item_discount),
                    "subtotal": str(item_subtotal),
                }
            )

        # Calculate discount amount
        if discount_type == "PERCENTAGE":
            discount_amount = (subtotal * discount_value) / Decimal("100.00")
        else:  # FIXED
            discount_amount = discount_value

        # Calculate tax and total
        discounted_subtotal = subtotal - discount_amount
        tax_amount = (discounted_subtotal * tax_rate) / Decimal("100.00")
        total = discounted_subtotal + tax_amount

        return Response(
            {
                "subtotal": str(subtotal),
                "discount_amount": str(discount_amount),
                "tax_amount": str(tax_amount),
                "total": str(total),
                "items": calculated_items,
            },
            status=status.HTTP_200_OK,
        )

    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "One or more inventory items not found."}, status=status.HTTP_400_BAD_REQUEST
        )
    except (ValueError, TypeError) as e:
        return Response(
            {"detail": f"Invalid numeric value: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
        )


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


# Receipt Generation Views


@require_http_methods(["GET"])
def receipt_html(request, sale_id, format_type="standard"):
    """
    Generate HTML receipt for browser viewing and printing.

    Implements Requirement 11.9: Receipt generation and printing
    Implements Requirement 35: Browser print API integration

    Args:
        sale_id: UUID of the sale
        format_type: 'standard' or 'thermal'
    """
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect("/accounts/login/")

    # Get sale with tenant check
    try:
        sale = (
            Sale.objects.select_related("customer", "branch", "terminal", "employee", "tenant")
            .prefetch_related("items__inventory_item")
            .get(id=sale_id, tenant=request.user.tenant)
        )
    except Sale.DoesNotExist:
        raise Http404("Receipt not found")

    # Generate HTML receipt
    html_content = ReceiptService.generate_receipt(
        sale=sale, format_type=format_type, output_format="html"
    ).decode("utf-8")

    return HttpResponse(html_content, content_type="text/html")


@require_http_methods(["GET"])
def receipt_pdf(request, sale_id, format_type="standard"):
    """
    Generate PDF receipt for download.

    Implements Requirement 11.9: Receipt generation and printing
    Implements Requirement 35: PDF receipt generation

    Args:
        sale_id: UUID of the sale
        format_type: 'standard' or 'thermal'
    """
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect("/accounts/login/")

    # Get sale with tenant check
    try:
        sale = (
            Sale.objects.select_related("customer", "branch", "terminal", "employee", "tenant")
            .prefetch_related("items__inventory_item")
            .get(id=sale_id, tenant=request.user.tenant)
        )
    except Sale.DoesNotExist:
        raise Http404("Receipt not found")

    # Generate PDF receipt
    pdf_bytes = ReceiptService.generate_receipt(
        sale=sale, format_type=format_type, output_format="pdf"
    )

    # Create response
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"receipt_{sale.sale_number}_{format_type}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_favorite_products(request):
    """
    Get favorite products for quick access in POS.

    Returns the most frequently sold products for the current user/branch.

    Implements Requirement 35.11: Provide quick access to favorite products
    """
    tenant = request.user.tenant
    limit = int(request.query_params.get("limit", "10"))

    # Get most frequently sold products from the last 30 days
    from datetime import timedelta

    from django.db.models import Count, Sum
    from django.utils import timezone

    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Query for most sold products
    favorite_products = (
        InventoryItem.objects.filter(
            tenant=tenant,
            is_active=True,
            quantity__gt=0,
            sale_items__sale__created_at__gte=thirty_days_ago,
            sale_items__sale__status="COMPLETED",
        )
        .annotate(sales_count=Count("sale_items"), total_quantity_sold=Sum("sale_items__quantity"))
        .order_by("-sales_count", "-total_quantity_sold")
        .select_related("category", "branch")[:limit]
    )

    # Serialize results
    results = []
    for item in favorite_products:
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
                "sales_count": item.sales_count,
                "is_favorite": True,
            }
        )

    return Response({"results": results}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_recent_transactions(request):
    """
    Get recent transactions for quick access in POS.

    Returns the most recent completed sales for reference.

    Implements Requirement 35.11: Provide quick access to recent transactions
    """
    tenant = request.user.tenant
    limit = int(request.query_params.get("limit", "10"))

    # Get recent completed sales
    recent_sales = (
        Sale.objects.filter(tenant=tenant, status="COMPLETED")
        .select_related("customer", "branch", "terminal", "employee")
        .prefetch_related("items__inventory_item")
        .order_by("-created_at")[:limit]
    )

    serializer = SaleListSerializer(recent_sales, many=True)
    return Response({"results": serializer.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def pos_offline_sync_validation(request):
    """
    Validate offline transactions before sync to detect conflicts.

    This endpoint is called during offline sync to check if inventory
    is still available for offline transactions.

    Request body:
    {
        "transactions": [
            {
                "id": "offline_transaction_id",
                "items": [
                    {
                        "inventory_item_id": "uuid",
                        "quantity": 1
                    }
                ]
            }
        ]
    }

    Response:
    {
        "validation_results": [
            {
                "transaction_id": "offline_transaction_id",
                "valid": true/false,
                "conflicts": [
                    {
                        "inventory_item_id": "uuid",
                        "requested_quantity": 1,
                        "available_quantity": 0,
                        "conflict_type": "insufficient_inventory"
                    }
                ]
            }
        ]
    }

    Implements Requirement 35: Conflict resolution for inventory sold offline at multiple terminals
    """
    tenant = request.user.tenant
    transactions_data = request.data.get("transactions", [])

    if not transactions_data:
        return Response(
            {"detail": "Transactions list is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    validation_results = []

    for transaction_data in transactions_data:
        transaction_id = transaction_data.get("id")
        items_data = transaction_data.get("items", [])

        result = {"transaction_id": transaction_id, "valid": True, "conflicts": []}

        for item_data in items_data:
            inventory_item_id = item_data.get("inventory_item_id")
            requested_quantity = item_data.get("quantity", 1)

            try:
                inventory_item = InventoryItem.objects.select_for_update().get(
                    id=inventory_item_id, tenant=tenant, is_active=True
                )

                # Check if sufficient inventory is available
                if inventory_item.quantity < requested_quantity:
                    result["valid"] = False
                    result["conflicts"].append(
                        {
                            "inventory_item_id": inventory_item_id,
                            "requested_quantity": requested_quantity,
                            "available_quantity": inventory_item.quantity,
                            "conflict_type": "insufficient_inventory",
                            "item_name": inventory_item.name,
                            "item_sku": inventory_item.sku,
                        }
                    )

                # Check for serialized items
                if inventory_item.serial_number and requested_quantity > 1:
                    result["valid"] = False
                    result["conflicts"].append(
                        {
                            "inventory_item_id": inventory_item_id,
                            "requested_quantity": requested_quantity,
                            "available_quantity": 1,
                            "conflict_type": "serialized_item_multiple_quantity",
                            "item_name": inventory_item.name,
                            "item_sku": inventory_item.sku,
                        }
                    )

            except InventoryItem.DoesNotExist:
                result["valid"] = False
                result["conflicts"].append(
                    {
                        "inventory_item_id": inventory_item_id,
                        "requested_quantity": requested_quantity,
                        "available_quantity": 0,
                        "conflict_type": "item_not_found",
                        "item_name": "Unknown",
                        "item_sku": "Unknown",
                    }
                )

        validation_results.append(result)

    return Response({"validation_results": validation_results}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def generate_receipt_after_sale(request, sale_id):
    """
    Generate receipt immediately after sale completion.

    This endpoint is called by the POS interface after a successful sale
    to generate and optionally print the receipt.

    Request body:
    {
        "format_type": "standard|thermal",
        "auto_print": true|false,
        "save_receipt": true|false
    }

    Response:
    {
        "receipt_url": "/receipts/html/uuid/standard/",
        "pdf_url": "/receipts/pdf/uuid/standard/",
        "receipt_saved": true|false,
        "file_path": "/path/to/saved/receipt.pdf"
    }

    Implements Requirement 11.9: Receipt generation and printing
    """
    set_tenant_context(request.user.tenant.id)

    try:
        sale = Sale.objects.select_related(
            "customer", "branch", "terminal", "employee", "tenant"
        ).get(id=sale_id, tenant=request.user.tenant)
    except Sale.DoesNotExist:
        return Response({"detail": "Sale not found."}, status=status.HTTP_404_NOT_FOUND)

    format_type = request.data.get("format_type", "standard")
    auto_print = request.data.get("auto_print", False)
    save_receipt = request.data.get("save_receipt", True)

    # Validate format type
    if format_type not in ["standard", "thermal"]:
        return Response(
            {"detail": "Invalid format_type. Must be 'standard' or 'thermal'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Generate receipt URLs
        receipt_url = f"/receipts/html/{sale_id}/{format_type}/"
        pdf_url = f"/receipts/pdf/{sale_id}/{format_type}/"

        # Add auto_print parameter if requested
        if auto_print:
            receipt_url += "?auto_print=true"

        response_data = {
            "receipt_url": receipt_url,
            "pdf_url": pdf_url,
            "receipt_saved": False,
            "file_path": None,
        }

        # Save receipt to file if requested
        if save_receipt:
            try:
                file_path = ReceiptService.save_receipt(sale, format_type)
                response_data["receipt_saved"] = True
                response_data["file_path"] = file_path
            except Exception as e:
                # Log error but don't fail the request
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to save receipt: {str(e)}")

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Receipt generation failed: {str(e)}", exc_info=True)

        return Response(
            {"detail": f"Receipt generation failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
