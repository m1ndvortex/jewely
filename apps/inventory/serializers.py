"""
Serializers for inventory models.

Implements Requirement 9: Advanced Inventory Management
"""

from rest_framework import serializers

from .models import InventoryItem, InventoryTransfer, InventoryTransferItem, ProductCategory


class ProductCategorySerializer(serializers.ModelSerializer):
    """Serializer for ProductCategory model."""

    full_path = serializers.CharField(source="get_full_path", read_only=True)
    subcategories_count = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ProductCategory
        fields = [
            "id",
            "tenant",
            "name",
            "parent",
            "full_path",
            "description",
            "is_active",
            "subcategories_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "full_path"]

    def get_subcategories_count(self, obj):
        """Get count of subcategories."""
        return obj.subcategories.count()

    def validate(self, data):
        """Validate category data."""
        # Prevent circular parent relationships
        if "parent" in data and data["parent"]:
            parent = data["parent"]
            if parent == self.instance:
                raise serializers.ValidationError(
                    {"parent": "A category cannot be its own parent."}
                )

            # Check for circular reference
            current = parent
            while current:
                if current == self.instance:
                    raise serializers.ValidationError(
                        {"parent": "Circular parent relationship detected."}
                    )
                current = current.parent

        return data


class InventoryItemListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for inventory item lists."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    total_value = serializers.DecimalField(
        source="calculate_total_value",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "sku",
            "name",
            "category",
            "category_name",
            "branch",
            "branch_name",
            "karat",
            "weight_grams",
            "quantity",
            "min_quantity",
            "cost_price",
            "selling_price",
            "is_low_stock",
            "is_out_of_stock",
            "total_value",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InventoryItemDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for inventory item detail view."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    category_full_path = serializers.CharField(source="category.get_full_path", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.company_name", read_only=True)

    # Computed fields
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    is_serialized = serializers.BooleanField(read_only=True)
    is_lot_tracked = serializers.BooleanField(read_only=True)
    total_value = serializers.DecimalField(
        source="calculate_total_value",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    total_selling_value = serializers.DecimalField(
        source="calculate_total_selling_value",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    profit_margin = serializers.DecimalField(
        source="calculate_profit_margin",
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "sku",
            "name",
            "category",
            "category_name",
            "category_full_path",
            "description",
            "karat",
            "weight_grams",
            "craftsmanship_level",
            "cost_price",
            "selling_price",
            "markup_percentage",
            "quantity",
            "min_quantity",
            "branch",
            "branch_name",
            "serial_number",
            "lot_number",
            "barcode",
            "qr_code",
            "supplier_name",
            "supplier_sku",
            "notes",
            "is_active",
            "is_low_stock",
            "is_out_of_stock",
            "is_serialized",
            "is_lot_tracked",
            "total_value",
            "total_selling_value",
            "profit_margin",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "markup_percentage",
            "created_at",
            "updated_at",
        ]


class InventoryItemCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating inventory items."""

    class Meta:
        model = InventoryItem
        fields = [
            "tenant",
            "sku",
            "name",
            "category",
            "description",
            "karat",
            "weight_grams",
            "craftsmanship_level",
            "cost_price",
            "selling_price",
            "quantity",
            "min_quantity",
            "branch",
            "serial_number",
            "lot_number",
            "barcode",
            "qr_code",
            "supplier_name",
            "supplier_sku",
            "notes",
            "is_active",
        ]

    def validate_sku(self, value):
        """Validate SKU uniqueness within tenant."""
        tenant = self.initial_data.get("tenant")
        if not tenant:
            tenant = (
                self.context.get("request").user.tenant_id if self.context.get("request") else None
            )

        # Check for existing SKU
        queryset = InventoryItem.objects.filter(tenant_id=tenant, sku=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "An item with this SKU already exists for this tenant."
            )

        return value

    def validate_barcode(self, value):
        """Validate barcode uniqueness."""
        if value:
            queryset = InventoryItem.objects.filter(barcode=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError("An item with this barcode already exists.")

        return value

    def validate(self, data):
        """Validate inventory item data."""
        # Validate selling price is greater than cost price
        cost_price = data.get("cost_price", self.instance.cost_price if self.instance else None)
        selling_price = data.get(
            "selling_price", self.instance.selling_price if self.instance else None
        )

        if cost_price and selling_price and selling_price < cost_price:
            raise serializers.ValidationError(
                {"selling_price": "Selling price should be greater than or equal to cost price."}
            )

        # Validate branch belongs to tenant
        branch = data.get("branch", self.instance.branch if self.instance else None)
        tenant = data.get("tenant", self.instance.tenant if self.instance else None)

        if branch and tenant and branch.tenant_id != tenant.id:
            raise serializers.ValidationError({"branch": "Branch must belong to the same tenant."})

        # Validate category belongs to tenant
        category = data.get("category", self.instance.category if self.instance else None)

        if category and tenant and category.tenant_id != tenant.id:
            raise serializers.ValidationError(
                {"category": "Category must belong to the same tenant."}
            )

        # Validate serialized items have quantity of 1 or 0
        serial_number = data.get(
            "serial_number", self.instance.serial_number if self.instance else None
        )
        quantity = data.get("quantity", self.instance.quantity if self.instance else None)

        if serial_number and quantity and quantity > 1:
            raise serializers.ValidationError(
                {
                    "quantity": "Serialized items (with serial number) can only have quantity of 0 or 1."
                }
            )

        return data


class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustment operations."""

    ADJUSTMENT_ADD = "ADD"
    ADJUSTMENT_DEDUCT = "DEDUCT"
    ADJUSTMENT_SET = "SET"

    ADJUSTMENT_TYPE_CHOICES = [
        (ADJUSTMENT_ADD, "Add to stock"),
        (ADJUSTMENT_DEDUCT, "Deduct from stock"),
        (ADJUSTMENT_SET, "Set stock level"),
    ]

    adjustment_type = serializers.ChoiceField(choices=ADJUSTMENT_TYPE_CHOICES)
    quantity = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_quantity(self, value):
        """Validate quantity is positive."""
        if value < 0:
            raise serializers.ValidationError("Quantity must be a positive number.")
        return value

    def validate(self, data):
        """Validate stock adjustment."""
        adjustment_type = data.get("adjustment_type")
        quantity = data.get("quantity")
        inventory_item = self.context.get("inventory_item")

        if not inventory_item:
            raise serializers.ValidationError("Inventory item is required.")

        # For deduction, check if sufficient stock is available
        if adjustment_type == self.ADJUSTMENT_DEDUCT:
            if not inventory_item.can_deduct_quantity(quantity):
                raise serializers.ValidationError(
                    {
                        "quantity": f"Insufficient stock. Available: {inventory_item.quantity}, "
                        f"Requested: {quantity}"
                    }
                )

        # For serialized items, validate quantity constraints
        if inventory_item.is_serialized():
            if adjustment_type == self.ADJUSTMENT_SET and quantity > 1:
                raise serializers.ValidationError(
                    {"quantity": "Serialized items can only have quantity of 0 or 1."}
                )
            if adjustment_type == self.ADJUSTMENT_ADD and quantity > 1:
                raise serializers.ValidationError(
                    {"quantity": "Cannot add more than 1 unit to a serialized item."}
                )

        return data

    def save(self, inventory_item):
        """Apply the stock adjustment."""
        adjustment_type = self.validated_data["adjustment_type"]
        quantity = self.validated_data["quantity"]
        reason = self.validated_data.get("reason", "")

        if adjustment_type == self.ADJUSTMENT_ADD:
            inventory_item.add_quantity(quantity, reason)
        elif adjustment_type == self.ADJUSTMENT_DEDUCT:
            inventory_item.deduct_quantity(quantity, reason)
        elif adjustment_type == self.ADJUSTMENT_SET:
            # Set to specific quantity
            inventory_item.quantity = quantity
            inventory_item.save(update_fields=["quantity", "updated_at"])

        return inventory_item


# Inventory Transfer Serializers


class InventoryTransferItemSerializer(serializers.Serializer):
    """Serializer for inventory transfer items (nested in transfer)."""

    inventory_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_inventory_item_id(self, value):
        """Validate that inventory item exists and belongs to tenant."""
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is required.")

        try:
            InventoryItem.objects.get(id=value, tenant=request.user.tenant)
            return value
        except InventoryItem.DoesNotExist:
            raise serializers.ValidationError(
                "Inventory item not found or does not belong to your tenant."
            )


class InventoryTransferItemDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for transfer items (for display)."""

    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    total_value = serializers.DecimalField(
        source="calculate_value",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    discrepancy_quantity = serializers.IntegerField(
        source="get_discrepancy_quantity",
        read_only=True,
    )

    class Meta:
        model = InventoryTransferItem
        fields = [
            "id",
            "inventory_item",
            "inventory_item_sku",
            "inventory_item_name",
            "quantity",
            "received_quantity",
            "has_discrepancy",
            "discrepancy_notes",
            "discrepancy_quantity",
            "unit_cost",
            "total_value",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InventoryTransferListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for transfer lists."""

    from .models import InventoryTransfer

    from_branch_name = serializers.CharField(source="from_branch.name", read_only=True)
    to_branch_name = serializers.CharField(source="to_branch.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = InventoryTransfer
        fields = [
            "id",
            "transfer_number",
            "from_branch",
            "from_branch_name",
            "to_branch",
            "to_branch_name",
            "status",
            "status_display",
            "requested_by",
            "requested_by_name",
            "requires_approval",
            "total_value",
            "items_count",
            "created_at",
            "approved_at",
            "shipped_at",
            "received_at",
        ]
        read_only_fields = ["id", "transfer_number", "created_at"]

    def get_items_count(self, obj):
        """Get count of items in transfer."""
        return obj.items.count()


class InventoryTransferDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for transfer detail view."""

    from .models import InventoryTransfer

    from_branch_name = serializers.CharField(source="from_branch.name", read_only=True)
    to_branch_name = serializers.CharField(source="to_branch.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)
    rejected_by_name = serializers.CharField(source="rejected_by.username", read_only=True)
    shipped_by_name = serializers.CharField(source="shipped_by.username", read_only=True)
    received_by_name = serializers.CharField(source="received_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = InventoryTransferItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryTransfer
        fields = [
            "id",
            "transfer_number",
            "from_branch",
            "from_branch_name",
            "to_branch",
            "to_branch_name",
            "status",
            "status_display",
            "requested_by",
            "requested_by_name",
            "approved_by",
            "approved_by_name",
            "rejected_by",
            "rejected_by_name",
            "shipped_by",
            "shipped_by_name",
            "received_by",
            "received_by_name",
            "requires_approval",
            "total_value",
            "notes",
            "rejection_reason",
            "items",
            "created_at",
            "approved_at",
            "rejected_at",
            "shipped_at",
            "received_at",
        ]
        read_only_fields = ["id", "transfer_number", "created_at"]


class InventoryTransferCreateSerializer(serializers.Serializer):
    """Serializer for creating inventory transfers."""

    from_branch_id = serializers.UUIDField()
    to_branch_id = serializers.UUIDField()
    items = InventoryTransferItemSerializer(many=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    approval_threshold = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=10000.00,
        required=False,
    )

    def validate_from_branch_id(self, value):
        """Validate from_branch exists and belongs to tenant."""
        from apps.core.models import Branch

        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is required.")

        try:
            Branch.objects.get(id=value, tenant=request.user.tenant)
            return value
        except Branch.DoesNotExist:
            raise serializers.ValidationError(
                "Source branch not found or does not belong to your tenant."
            )

    def validate_to_branch_id(self, value):
        """Validate to_branch exists and belongs to tenant."""
        from apps.core.models import Branch

        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context is required.")

        try:
            Branch.objects.get(id=value, tenant=request.user.tenant)
            return value
        except Branch.DoesNotExist:
            raise serializers.ValidationError(
                "Destination branch not found or does not belong to your tenant."
            )

    def validate_items(self, value):
        """Validate transfer items."""
        if not value:
            raise serializers.ValidationError("At least one item is required for transfer.")

        # Check for duplicate items
        item_ids = [item_data["inventory_item_id"] for item_data in value]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Duplicate items are not allowed in a transfer.")

        return value

    def validate(self, data):
        """Validate transfer data."""
        # Validate from_branch != to_branch
        if data["from_branch_id"] == data["to_branch_id"]:
            raise serializers.ValidationError(
                {"to_branch_id": "Source and destination branches must be different."}
            )

        # Validate all items belong to from_branch and have sufficient quantity
        from_branch_id = data["from_branch_id"]
        request = self.context.get("request")

        for item_data in data["items"]:
            try:
                inventory_item = InventoryItem.objects.get(
                    id=item_data["inventory_item_id"],
                    tenant=request.user.tenant,
                )

                # Check if item is from the source branch
                if inventory_item.branch_id != from_branch_id:
                    raise serializers.ValidationError(
                        {
                            "items": f"Item {inventory_item.sku} is not in the source branch. "
                            f"It is in {inventory_item.branch.name}."
                        }
                    )

                # Check if sufficient quantity is available
                if not inventory_item.can_deduct_quantity(item_data["quantity"]):
                    raise serializers.ValidationError(
                        {
                            "items": f"Insufficient quantity for item {inventory_item.sku}. "
                            f"Available: {inventory_item.quantity}, Requested: {item_data['quantity']}"
                        }
                    )

            except InventoryItem.DoesNotExist:
                raise serializers.ValidationError(
                    {"items": f"Inventory item {item_data['inventory_item_id']} not found."}
                )

        return data

    def create(self, validated_data):
        """Create inventory transfer with items."""
        from decimal import Decimal

        from django.db import transaction

        from apps.core.models import Branch

        from .models import InventoryTransfer, InventoryTransferItem

        items_data = validated_data.pop("items")
        approval_threshold = validated_data.pop("approval_threshold", Decimal("10000.00"))

        # Get branches
        from_branch = Branch.objects.get(id=validated_data.pop("from_branch_id"))
        to_branch = Branch.objects.get(id=validated_data.pop("to_branch_id"))

        with transaction.atomic():
            # Create transfer
            transfer = InventoryTransfer.objects.create(
                from_branch=from_branch,
                to_branch=to_branch,
                notes=validated_data.get("notes", ""),
                **validated_data,
            )

            # Create transfer items and calculate total value
            total_value = Decimal("0.00")
            for item_data in items_data:
                inventory_item = InventoryItem.objects.get(id=item_data["inventory_item_id"])

                transfer_item = InventoryTransferItem.objects.create(
                    transfer=transfer,
                    inventory_item=inventory_item,
                    quantity=item_data["quantity"],
                    unit_cost=inventory_item.cost_price,
                    notes=item_data.get("notes", ""),
                )

                total_value += transfer_item.calculate_value()

            # Update transfer with total value and approval requirement
            transfer.total_value = total_value
            transfer.requires_approval = total_value >= approval_threshold
            transfer.save(update_fields=["total_value", "requires_approval"])

        return transfer
