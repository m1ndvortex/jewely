"""
Views for inventory management.

Implements Requirement 9: Advanced Inventory Management
- Inventory list view with search and filters
- Inventory detail view
- Inventory create/edit operations with validation
- Stock adjustment functionality
"""

from django.db.models import F, Q

from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.core.permissions import HasTenantAccess
from apps.core.tenant_context import set_tenant_context

from .models import InventoryItem, ProductCategory
from .serializers import (
    InventoryItemCreateUpdateSerializer,
    InventoryItemDetailSerializer,
    InventoryItemListSerializer,
    ProductCategorySerializer,
    StockAdjustmentSerializer,
)


class TenantContextMixin:
    """Mixin to set tenant context for API views."""

    def initial(self, request, *args, **kwargs):
        """Set tenant context after authentication."""
        super().initial(request, *args, **kwargs)
        if hasattr(request, "user") and hasattr(request.user, "tenant") and request.user.tenant:
            set_tenant_context(request.user.tenant.id)


class InventoryItemListView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for listing inventory items with search and filters.

    Supports:
    - Search by SKU, name, serial number, lot number, barcode
    - Filter by category, branch, karat, is_active, low_stock, out_of_stock
    - Ordering by various fields
    """

    serializer_class = InventoryItemListSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        "sku",
        "name",
        "quantity",
        "cost_price",
        "selling_price",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):  # noqa: C901
        """
        Get inventory items for the current user's tenant with filters.
        """
        user = self.request.user
        queryset = InventoryItem.objects.filter(tenant=user.tenant).select_related(
            "category", "branch", "tenant"
        )

        # Search functionality
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(sku__icontains=search)
                | Q(name__icontains=search)
                | Q(serial_number__icontains=search)
                | Q(lot_number__icontains=search)
                | Q(barcode__icontains=search)
                | Q(description__icontains=search)
            )

        # Filter by category
        category_id = self.request.query_params.get("category", None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Filter by branch
        branch_id = self.request.query_params.get("branch", None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        # Filter by karat
        karat = self.request.query_params.get("karat", None)
        if karat:
            queryset = queryset.filter(karat=karat)

        # Filter by craftsmanship level
        craftsmanship = self.request.query_params.get("craftsmanship", None)
        if craftsmanship:
            queryset = queryset.filter(craftsmanship_level=craftsmanship)

        # Filter by active status
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            is_active_bool = is_active.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(is_active=is_active_bool)

        # Filter by low stock
        low_stock = self.request.query_params.get("low_stock", None)
        if low_stock and low_stock.lower() in ["true", "1", "yes"]:
            queryset = queryset.filter(quantity__lte=F("min_quantity"))

        # Filter by out of stock
        out_of_stock = self.request.query_params.get("out_of_stock", None)
        if out_of_stock and out_of_stock.lower() in ["true", "1", "yes"]:
            queryset = queryset.filter(quantity=0)

        # Filter by serialized items
        serialized = self.request.query_params.get("serialized", None)
        if serialized and serialized.lower() in ["true", "1", "yes"]:
            queryset = queryset.exclude(serial_number__isnull=True).exclude(serial_number="")

        # Filter by lot tracked items
        lot_tracked = self.request.query_params.get("lot_tracked", None)
        if lot_tracked and lot_tracked.lower() in ["true", "1", "yes"]:
            queryset = queryset.exclude(lot_number__isnull=True).exclude(lot_number="")

        return queryset


class InventoryItemDetailView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single inventory item.
    """

    serializer_class = InventoryItemDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get inventory items for the current user's tenant."""
        user = self.request.user
        return InventoryItem.objects.filter(tenant=user.tenant).select_related(
            "category", "branch", "tenant"
        )


class InventoryItemCreateView(TenantContextMixin, generics.CreateAPIView):
    """
    API endpoint for creating a new inventory item.
    """

    serializer_class = InventoryItemCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant from current user."""
        serializer.save(tenant=self.request.user.tenant)


class InventoryItemUpdateView(TenantContextMixin, generics.UpdateAPIView):
    """
    API endpoint for updating an inventory item.
    """

    serializer_class = InventoryItemCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get inventory items for the current user's tenant."""
        user = self.request.user
        return InventoryItem.objects.filter(tenant=user.tenant)


class InventoryItemDeleteView(TenantContextMixin, generics.DestroyAPIView):
    """
    API endpoint for deleting (soft delete) an inventory item.
    """

    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get inventory items for the current user's tenant."""
        user = self.request.user
        return InventoryItem.objects.filter(tenant=user.tenant)

    def perform_destroy(self, instance):
        """Soft delete by setting is_active to False."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def stock_adjustment(request, item_id):
    """
    API endpoint for adjusting stock levels.

    Supports three types of adjustments:
    - ADD: Add quantity to current stock
    - DEDUCT: Deduct quantity from current stock
    - SET: Set stock to a specific level

    Request body:
    {
        "adjustment_type": "ADD|DEDUCT|SET",
        "quantity": <number>,
        "reason": "<optional reason>"
    }
    """
    # Get the inventory item
    try:
        inventory_item = InventoryItem.objects.select_for_update().get(
            id=item_id, tenant=request.user.tenant
        )
    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "Inventory item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Validate the adjustment
    serializer = StockAdjustmentSerializer(
        data=request.data, context={"inventory_item": inventory_item}
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Apply the adjustment
    try:
        updated_item = serializer.save(inventory_item)
        return Response(
            {
                "detail": "Stock adjusted successfully.",
                "item": InventoryItemDetailSerializer(updated_item).data,
            },
            status=status.HTTP_200_OK,
        )
    except ValueError as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


# Product Category Views


class ProductCategoryListView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for listing product categories.
    """

    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Get categories for the current user's tenant."""
        user = self.request.user
        queryset = ProductCategory.objects.filter(tenant=user.tenant).select_related("parent")

        # Filter by active status
        is_active = self.request.query_params.get("is_active", None)
        if is_active is not None:
            is_active_bool = is_active.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(is_active=is_active_bool)

        # Filter by parent (get root categories or subcategories)
        parent_id = self.request.query_params.get("parent", None)
        if parent_id == "null" or parent_id == "":
            queryset = queryset.filter(parent__isnull=True)
        elif parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        return queryset


class ProductCategoryDetailView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single product category.
    """

    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get categories for the current user's tenant."""
        user = self.request.user
        return ProductCategory.objects.filter(tenant=user.tenant).select_related("parent")


class ProductCategoryCreateView(TenantContextMixin, generics.CreateAPIView):
    """
    API endpoint for creating a new product category.
    """

    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant from current user."""
        serializer.save(tenant=self.request.user.tenant)


class ProductCategoryUpdateView(TenantContextMixin, generics.UpdateAPIView):
    """
    API endpoint for updating a product category.
    """

    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get categories for the current user's tenant."""
        user = self.request.user
        return ProductCategory.objects.filter(tenant=user.tenant)


class ProductCategoryDeleteView(TenantContextMixin, generics.DestroyAPIView):
    """
    API endpoint for deleting (soft delete) a product category.
    """

    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    lookup_field = "id"

    def get_queryset(self):
        """Get categories for the current user's tenant."""
        user = self.request.user
        return ProductCategory.objects.filter(tenant=user.tenant)

    def perform_destroy(self, instance):
        """Soft delete by setting is_active to False."""
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


# Barcode and QR Code Generation Views


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def generate_barcode(request, item_id):
    """
    Generate a barcode for an inventory item.

    Query parameters:
    - format: Barcode format (code128, ean13, ean8, code39) - default: code128
    - data_type: What to encode (sku, serial, barcode) - default: sku

    Returns:
        PNG image of the barcode
    """
    from django.http import HttpResponse

    from .barcode_utils import BarcodeGenerator

    # Get the inventory item
    try:
        inventory_item = InventoryItem.objects.get(id=item_id, tenant=request.user.tenant)
    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "Inventory item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get parameters
    barcode_format = request.query_params.get("format", "code128")
    data_type = request.query_params.get("data_type", "sku")

    # Determine what data to encode
    if data_type == "serial" and inventory_item.serial_number:
        data = inventory_item.serial_number
    elif data_type == "barcode" and inventory_item.barcode:
        data = inventory_item.barcode
    else:
        data = inventory_item.sku

    # Generate barcode
    try:
        barcode_bytes, mime_type = BarcodeGenerator.generate_barcode(data, barcode_format)

        response = HttpResponse(barcode_bytes, content_type=mime_type)
        response["Content-Disposition"] = f'inline; filename="{inventory_item.sku}_barcode.png"'
        return response

    except ValueError as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def generate_qr_code(request, item_id):
    """
    Generate a QR code for an inventory item.

    Query parameters:
    - data_type: What to encode (full, url, sku) - default: full
    - url: Custom URL to encode (if data_type=url)

    Returns:
        PNG image of the QR code
    """
    import json

    from django.http import HttpResponse

    from .barcode_utils import QRCodeGenerator

    # Get the inventory item
    try:
        inventory_item = InventoryItem.objects.get(id=item_id, tenant=request.user.tenant)
    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "Inventory item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get parameters
    data_type = request.query_params.get("data_type", "full")

    # Determine what data to encode
    if data_type == "url":
        # Custom URL provided
        url = request.query_params.get("url", "")
        if not url:
            return Response(
                {"detail": "URL parameter required for data_type=url"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = url
    elif data_type == "sku":
        # Just the SKU
        data = inventory_item.sku
    else:
        # Full item data
        item_data = {
            "sku": inventory_item.sku,
            "name": inventory_item.name,
            "karat": inventory_item.karat,
            "weight": str(inventory_item.weight_grams),
            "price": str(inventory_item.selling_price),
        }
        if inventory_item.serial_number:
            item_data["serial"] = inventory_item.serial_number
        if inventory_item.barcode:
            item_data["barcode"] = inventory_item.barcode

        data = json.dumps(item_data, separators=(",", ":"))

    # Generate QR code
    try:
        qr_bytes, mime_type = QRCodeGenerator.generate_qr_code(data)

        response = HttpResponse(qr_bytes, content_type=mime_type)
        response["Content-Disposition"] = f'inline; filename="{inventory_item.sku}_qrcode.png"'
        return response

    except Exception as e:
        return Response(
            {"detail": f"Error generating QR code: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def generate_product_label(request, item_id):
    """
    Generate a printable product label with barcode.

    Query parameters:
    - size: Label size (small, medium, large) - default: medium
    - dpi: Print resolution (150, 300, 600) - default: 300

    Returns:
        PNG image of the printable label
    """
    from django.http import HttpResponse

    from .barcode_utils import BarcodeGenerator, LabelGenerator

    # Get the inventory item
    try:
        inventory_item = InventoryItem.objects.get(id=item_id, tenant=request.user.tenant)
    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "Inventory item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get parameters
    size_param = request.query_params.get("size", "medium")
    dpi = int(request.query_params.get("dpi", "300"))

    # Map size parameter to dimensions
    size_map = {
        "small": LabelGenerator.LABEL_SMALL,
        "medium": LabelGenerator.LABEL_MEDIUM,
        "large": LabelGenerator.LABEL_LARGE,
    }
    label_size = size_map.get(size_param, LabelGenerator.LABEL_MEDIUM)

    # Generate barcode first
    try:
        barcode_bytes, _ = BarcodeGenerator.generate_barcode_for_sku(inventory_item.sku)
    except ValueError as e:
        return Response(
            {"detail": f"Error generating barcode: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Format price
    price_str = f"${inventory_item.selling_price:,.2f}"

    # Generate label
    try:
        label_bytes, mime_type = LabelGenerator.create_product_label(
            sku=inventory_item.sku,
            name=inventory_item.name,
            price=price_str,
            barcode_data=barcode_bytes,
            label_size=label_size,
            dpi=dpi,
        )

        response = HttpResponse(label_bytes, content_type=mime_type)
        response["Content-Disposition"] = f'inline; filename="{inventory_item.sku}_label.png"'
        return response

    except Exception as e:
        return Response(
            {"detail": f"Error generating label: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def generate_qr_label(request, item_id):
    """
    Generate a printable label with QR code.

    Query parameters:
    - size: Label size (small, medium, large) - default: medium
    - dpi: Print resolution (150, 300, 600) - default: 300

    Returns:
        PNG image of the printable label
    """
    import json

    from django.http import HttpResponse

    from .barcode_utils import LabelGenerator, QRCodeGenerator

    # Get the inventory item
    try:
        inventory_item = InventoryItem.objects.get(id=item_id, tenant=request.user.tenant)
    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": "Inventory item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get parameters
    size_param = request.query_params.get("size", "medium")
    dpi = int(request.query_params.get("dpi", "300"))

    # Map size parameter to dimensions
    size_map = {
        "small": LabelGenerator.LABEL_SMALL,
        "medium": LabelGenerator.LABEL_MEDIUM,
        "large": LabelGenerator.LABEL_LARGE,
    }
    label_size = size_map.get(size_param, LabelGenerator.LABEL_MEDIUM)

    # Prepare QR code data
    item_data = {
        "sku": inventory_item.sku,
        "name": inventory_item.name,
        "karat": inventory_item.karat,
        "weight": str(inventory_item.weight_grams),
        "price": str(inventory_item.selling_price),
    }
    if inventory_item.serial_number:
        item_data["serial"] = inventory_item.serial_number

    qr_data_str = json.dumps(item_data, separators=(",", ":"))

    # Generate QR code first
    try:
        qr_bytes, _ = QRCodeGenerator.generate_qr_code(qr_data_str)
    except Exception as e:
        return Response(
            {"detail": f"Error generating QR code: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Generate label
    try:
        label_bytes, mime_type = LabelGenerator.create_qr_label(
            title=inventory_item.name[:30],
            subtitle=f"SKU: {inventory_item.sku}",
            qr_data=qr_bytes,
            label_size=label_size,
            dpi=dpi,
        )

        response = HttpResponse(label_bytes, content_type=mime_type)
        response["Content-Disposition"] = f'inline; filename="{inventory_item.sku}_qr_label.png"'
        return response

    except Exception as e:
        return Response(
            {"detail": f"Error generating label: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def lookup_by_barcode(request):
    """
    Look up an inventory item by barcode for quick scanning.

    Query parameters:
    - barcode: The barcode value to search for (required)

    Returns:
        Inventory item details if found

    This endpoint supports Requirement 35.6: "THE System SHALL support barcode
    scanning for quick item lookup"
    """
    barcode_value = request.query_params.get("barcode", "").strip()

    if not barcode_value:
        return Response(
            {"detail": "Barcode parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Look up item by barcode
    try:
        inventory_item = InventoryItem.objects.get(
            barcode=barcode_value, tenant=request.user.tenant, is_active=True
        )

        serializer = InventoryItemDetailSerializer(inventory_item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except InventoryItem.DoesNotExist:
        return Response(
            {"detail": f"No inventory item found with barcode: {barcode_value}"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except InventoryItem.MultipleObjectsReturned:
        # This shouldn't happen if barcode is unique, but handle it
        return Response(
            {
                "detail": f"Multiple items found with barcode: {barcode_value}. Please contact support."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Inventory Reports


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def inventory_valuation_report(request):
    """
    Generate inventory valuation report.

    Shows total inventory value at cost and selling price,
    broken down by category and branch.

    Query parameters:
    - branch: Optional branch ID filter
    - category: Optional category ID filter

    Implements Requirement 9: Advanced Inventory Management
    - Inventory valuation using configurable methods
    - Inventory reports including stock valuation

    Implements Requirement 15: Advanced Reporting and Analytics
    - Pre-built reports for inventory metrics
    """
    from .reports import InventoryReportGenerator

    # Get filters
    branch_id = request.query_params.get("branch", None)
    category_id = request.query_params.get("category", None)

    # Generate report
    generator = InventoryReportGenerator(request.user.tenant)
    report_data = generator.get_inventory_valuation_report(
        branch_id=branch_id, category_id=category_id
    )

    return Response(report_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def low_stock_alert_report(request):
    """
    Generate low stock alert report.

    Shows items that are at or below their minimum quantity threshold.

    Query parameters:
    - branch: Optional branch ID filter
    - category: Optional category ID filter

    Implements Requirement 9: Advanced Inventory Management
    - Generate low stock alerts when inventory falls below defined thresholds
    """
    from .reports import InventoryReportGenerator

    # Get filters
    branch_id = request.query_params.get("branch", None)
    category_id = request.query_params.get("category", None)

    # Generate report
    generator = InventoryReportGenerator(request.user.tenant)
    report_data = generator.get_low_stock_alert_report(branch_id=branch_id, category_id=category_id)

    return Response(report_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def dead_stock_analysis_report(request):
    """
    Generate dead stock analysis report.

    Identifies items that haven't moved (sold) in a specified period.

    Query parameters:
    - days: Number of days to consider as "dead stock" (default: 90)
    - branch: Optional branch ID filter
    - category: Optional category ID filter

    Implements Requirement 9: Advanced Inventory Management
    - Inventory reports including dead stock analysis

    Implements Requirement 15: Advanced Reporting and Analytics
    - Pre-built reports for inventory metrics
    """
    from .reports import InventoryReportGenerator

    # Get filters
    days_threshold = int(request.query_params.get("days", "90"))
    branch_id = request.query_params.get("branch", None)
    category_id = request.query_params.get("category", None)

    # Generate report
    generator = InventoryReportGenerator(request.user.tenant)
    report_data = generator.get_dead_stock_analysis_report(
        days_threshold=days_threshold, branch_id=branch_id, category_id=category_id
    )

    return Response(report_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def inventory_turnover_report(request):
    """
    Generate inventory turnover report.

    Shows inventory movement and turnover metrics.

    Query parameters:
    - period: Period to analyze in days (default: 30)
    - branch: Optional branch ID filter
    - category: Optional category ID filter

    Implements Requirement 9: Advanced Inventory Management
    - Inventory reports including inventory turnover

    Implements Requirement 15: Advanced Reporting and Analytics
    - Pre-built reports for inventory metrics
    """
    from .reports import InventoryReportGenerator

    # Get filters
    period_days = int(request.query_params.get("period", "30"))
    branch_id = request.query_params.get("branch", None)
    category_id = request.query_params.get("category", None)

    # Generate report
    generator = InventoryReportGenerator(request.user.tenant)
    report_data = generator.get_inventory_turnover_report(
        period_days=period_days, branch_id=branch_id, category_id=category_id
    )

    return Response(report_data, status=status.HTTP_200_OK)


# Inventory Transfer Views


class InventoryTransferListView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for listing inventory transfers with filters.

    Supports:
    - Filter by status, from_branch, to_branch
    - Search by transfer_number
    - Ordering by various fields

    Implements Requirement 14: Multi-Branch Management
    - Inter-branch inventory transfers with in-transit tracking
    """

    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["transfer_number", "created_at", "status", "total_value"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Get the appropriate serializer class."""
        from .serializers import InventoryTransferListSerializer

        return InventoryTransferListSerializer

    def get_queryset(self):
        """Get transfers for the current user's tenant with filters."""
        from .models import InventoryTransfer

        user = self.request.user
        queryset = InventoryTransfer.objects.filter(tenant=user.tenant).select_related(
            "from_branch",
            "to_branch",
            "requested_by",
            "approved_by",
            "shipped_by",
            "received_by",
        )

        # Search by transfer number
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(transfer_number__icontains=search)

        # Filter by status
        status_filter = self.request.query_params.get("status", None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by from_branch
        from_branch_id = self.request.query_params.get("from_branch", None)
        if from_branch_id:
            queryset = queryset.filter(from_branch_id=from_branch_id)

        # Filter by to_branch
        to_branch_id = self.request.query_params.get("to_branch", None)
        if to_branch_id:
            queryset = queryset.filter(to_branch_id=to_branch_id)

        # Filter by user's branch (show transfers involving their branch)
        my_branch = self.request.query_params.get("my_branch", None)
        if my_branch and my_branch.lower() in ["true", "1", "yes"] and user.branch:
            queryset = queryset.filter(Q(from_branch=user.branch) | Q(to_branch=user.branch))

        return queryset


class InventoryTransferDetailView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single inventory transfer with all items.
    """

    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def get_serializer_class(self):
        """Get the appropriate serializer class."""
        from .serializers import InventoryTransferDetailSerializer

        return InventoryTransferDetailSerializer

    lookup_field = "id"

    def get_queryset(self):
        """Get transfers for the current user's tenant."""
        from .models import InventoryTransfer

        user = self.request.user
        return (
            InventoryTransfer.objects.filter(tenant=user.tenant)
            .select_related(
                "from_branch",
                "to_branch",
                "requested_by",
                "approved_by",
                "shipped_by",
                "received_by",
            )
            .prefetch_related("items__inventory_item")
        )


class InventoryTransferCreateView(TenantContextMixin, generics.CreateAPIView):
    """
    API endpoint for creating a new inventory transfer request.

    Automatically determines if approval is required based on total value.
    """

    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def get_serializer_class(self):
        """Get the appropriate serializer class."""
        from .serializers import InventoryTransferCreateSerializer

        return InventoryTransferCreateSerializer

    def perform_create(self, serializer):
        """Set tenant and requested_by from current user."""
        serializer.save(tenant=self.request.user.tenant, requested_by=self.request.user)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def approve_transfer(request, transfer_id):
    """
    Approve a pending inventory transfer.

    Only managers/owners can approve transfers, and they cannot approve their own requests.

    Implements Requirement 14: Multi-Branch Management
    - Approval workflow for high-value transfers
    """
    from django.db import transaction

    from .models import InventoryTransfer

    # Get the transfer
    try:
        transfer = InventoryTransfer.objects.select_for_update().get(
            id=transfer_id, tenant=request.user.tenant
        )
    except InventoryTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if user can approve
    if not transfer.can_approve(request.user):
        return Response(
            {"detail": "You do not have permission to approve this transfer."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if transfer is in pending status
    if transfer.status != InventoryTransfer.PENDING:
        return Response(
            {
                "detail": f"Transfer cannot be approved. Current status: {transfer.get_status_display()}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Approve the transfer
    try:
        with transaction.atomic():
            transfer.approve(request.user)
            transfer.save()

        from .serializers import InventoryTransferDetailSerializer

        return Response(
            {
                "detail": "Transfer approved successfully.",
                "transfer": InventoryTransferDetailSerializer(transfer).data,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"detail": f"Error approving transfer: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def reject_transfer(request, transfer_id):
    """
    Reject a pending inventory transfer.

    Request body:
    {
        "reason": "Reason for rejection"
    }
    """
    from django.db import transaction

    from .models import InventoryTransfer

    # Get the transfer
    try:
        transfer = InventoryTransfer.objects.select_for_update().get(
            id=transfer_id, tenant=request.user.tenant
        )
    except InventoryTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if user can approve (same permission for reject)
    if not transfer.can_approve(request.user):
        return Response(
            {"detail": "You do not have permission to reject this transfer."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if transfer is in pending status
    if transfer.status != InventoryTransfer.PENDING:
        return Response(
            {
                "detail": f"Transfer cannot be rejected. Current status: {transfer.get_status_display()}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get rejection reason
    reason = request.data.get("reason", "")
    if not reason:
        return Response(
            {"detail": "Rejection reason is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Reject the transfer
    try:
        with transaction.atomic():
            transfer.reject(request.user, reason)
            transfer.save()

        from .serializers import InventoryTransferDetailSerializer

        return Response(
            {
                "detail": "Transfer rejected successfully.",
                "transfer": InventoryTransferDetailSerializer(transfer).data,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"detail": f"Error rejecting transfer: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def ship_transfer(request, transfer_id):
    """
    Mark an approved transfer as shipped/in transit.

    This deducts inventory from the source branch.
    Only users from the source branch can ship transfers.
    """
    from django.db import transaction

    from .models import InventoryTransfer

    # Get the transfer
    try:
        transfer = InventoryTransfer.objects.select_for_update().get(
            id=transfer_id, tenant=request.user.tenant
        )
    except InventoryTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if user can ship
    if not transfer.can_ship(request.user):
        return Response(
            {
                "detail": "You do not have permission to ship this transfer. Must be from source branch."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if transfer is in approved status
    if transfer.status != InventoryTransfer.APPROVED:
        return Response(
            {
                "detail": f"Transfer cannot be shipped. Current status: {transfer.get_status_display()}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Ship the transfer
    try:
        with transaction.atomic():
            transfer.mark_shipped(request.user)
            transfer.save()

        from .serializers import InventoryTransferDetailSerializer

        return Response(
            {
                "detail": "Transfer marked as shipped. Inventory deducted from source branch.",
                "transfer": InventoryTransferDetailSerializer(transfer).data,
            },
            status=status.HTTP_200_OK,
        )
    except ValueError as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"detail": f"Error shipping transfer: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def receive_transfer(request, transfer_id):
    """
    Mark a transfer as received at destination.

    This adds inventory to the destination branch.
    Only users from the destination branch can receive transfers.

    Request body (optional):
    {
        "discrepancies": {
            "<item_id>": <actual_quantity>,
            ...
        }
    }

    Implements Requirement 14: Multi-Branch Management
    - Receiving confirmation interface with discrepancy logging
    - Update inventory levels on transfer completion
    """
    from django.db import transaction

    from .models import InventoryTransfer

    # Get the transfer
    try:
        transfer = InventoryTransfer.objects.select_for_update().get(
            id=transfer_id, tenant=request.user.tenant
        )
    except InventoryTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if user can receive
    if not transfer.can_receive(request.user):
        return Response(
            {
                "detail": "You do not have permission to receive this transfer. Must be from destination branch."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if transfer is in transit status
    if transfer.status != InventoryTransfer.IN_TRANSIT:
        return Response(
            {
                "detail": f"Transfer cannot be received. Current status: {transfer.get_status_display()}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get discrepancies if any
    discrepancies = request.data.get("discrepancies", {})

    # Receive the transfer
    try:
        with transaction.atomic():
            transfer.mark_received(request.user, discrepancies)
            transfer.save()

        from .serializers import InventoryTransferDetailSerializer

        return Response(
            {
                "detail": "Transfer received successfully. Inventory added to destination branch.",
                "transfer": InventoryTransferDetailSerializer(transfer).data,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"detail": f"Error receiving transfer: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasTenantAccess])
def cancel_transfer(request, transfer_id):
    """
    Cancel a pending or approved transfer.

    Request body:
    {
        "reason": "Reason for cancellation"
    }
    """
    from django.db import transaction

    from .models import InventoryTransfer

    # Get the transfer
    try:
        transfer = InventoryTransfer.objects.select_for_update().get(
            id=transfer_id, tenant=request.user.tenant
        )
    except InventoryTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Check if transfer can be cancelled
    if transfer.status not in [InventoryTransfer.PENDING, InventoryTransfer.APPROVED]:
        return Response(
            {
                "detail": f"Transfer cannot be cancelled. Current status: {transfer.get_status_display()}"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get cancellation reason
    reason = request.data.get("reason", "")

    # Cancel the transfer
    try:
        with transaction.atomic():
            transfer.cancel(request.user, reason)
            transfer.save()

        from .serializers import InventoryTransferDetailSerializer

        return Response(
            {
                "detail": "Transfer cancelled successfully.",
                "transfer": InventoryTransferDetailSerializer(transfer).data,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"detail": f"Error cancelling transfer: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
