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

from .models import InventoryItem, ProductCategory
from .serializers import (
    InventoryItemCreateUpdateSerializer,
    InventoryItemDetailSerializer,
    InventoryItemListSerializer,
    ProductCategorySerializer,
    StockAdjustmentSerializer,
)


class InventoryItemListView(generics.ListAPIView):
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


class InventoryItemDetailView(generics.RetrieveAPIView):
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


class InventoryItemCreateView(generics.CreateAPIView):
    """
    API endpoint for creating a new inventory item.
    """

    serializer_class = InventoryItemCreateUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant from current user."""
        serializer.save(tenant=self.request.user.tenant)


class InventoryItemUpdateView(generics.UpdateAPIView):
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


class InventoryItemDeleteView(generics.DestroyAPIView):
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


class ProductCategoryListView(generics.ListAPIView):
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


class ProductCategoryDetailView(generics.RetrieveAPIView):
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


class ProductCategoryCreateView(generics.CreateAPIView):
    """
    API endpoint for creating a new product category.
    """

    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant from current user."""
        serializer.save(tenant=self.request.user.tenant)


class ProductCategoryUpdateView(generics.UpdateAPIView):
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


class ProductCategoryDeleteView(generics.DestroyAPIView):
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
