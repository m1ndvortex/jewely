"""
Serializers for sales app.

Implements Requirement 11: Point of Sale (POS) System
- Serializers for POS interface
- Sale creation and management
- Customer quick add
- Payment processing
"""

from decimal import Decimal

from django.db import transaction

from rest_framework import serializers

from apps.inventory.models import InventoryItem

from .models import Customer, Sale, SaleItem, Terminal


class CustomerQuickAddSerializer(serializers.ModelSerializer):
    """
    Serializer for quick customer creation during POS checkout.
    Only requires essential fields.
    """

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "first_name",
            "last_name",
            "phone",
            "email",
        ]
        read_only_fields = ["id", "customer_number"]

    def create(self, validated_data):
        """Generate customer number automatically."""
        tenant = self.context["request"].user.tenant

        # Generate customer number
        last_customer = Customer.objects.filter(tenant=tenant).order_by("-created_at").first()
        if last_customer and last_customer.customer_number:
            try:
                last_number = int(last_customer.customer_number.split("-")[-1])
                new_number = f"CUST-{last_number + 1:06d}"
            except (ValueError, IndexError):
                new_number = "CUST-000001"
        else:
            new_number = "CUST-000001"

        validated_data["customer_number"] = new_number
        validated_data["tenant"] = tenant

        return super().create(validated_data)


class CustomerListSerializer(serializers.ModelSerializer):
    """Serializer for customer list in POS."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "email",
            "loyalty_tier",
            "loyalty_points",
            "store_credit",
        ]


class TerminalListSerializer(serializers.ModelSerializer):
    """Serializer for terminal list."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Terminal
        fields = [
            "id",
            "terminal_id",
            "branch_name",
            "is_active",
        ]


class SaleItemCreateSerializer(serializers.Serializer):
    """Serializer for creating sale items."""

    inventory_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_inventory_item_id(self, value):
        """Validate that inventory item exists and belongs to tenant."""
        tenant = self.context["request"].user.tenant
        try:
            InventoryItem.objects.get(id=value, tenant=tenant, is_active=True)
            return value
        except InventoryItem.DoesNotExist:
            raise serializers.ValidationError("Inventory item not found or inactive.")


class SaleCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a new sale through POS.

    Handles:
    - Sale creation with multiple items
    - Inventory deduction
    - Customer association
    - Payment processing
    - Tax and discount calculation
    """

    customer_id = serializers.UUIDField(required=False, allow_null=True)
    terminal_id = serializers.UUIDField()
    items = SaleItemCreateSerializer(many=True)
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHOD_CHOICES)
    payment_details = serializers.JSONField(required=False, default=dict)
    tax_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), required=False
    )
    discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=Sale.STATUS_CHOICES, default=Sale.COMPLETED, required=False
    )

    def validate_terminal_id(self, value):
        """Validate that terminal exists and is active."""
        tenant = self.context["request"].user.tenant
        try:
            Terminal.objects.get(id=value, branch__tenant=tenant, is_active=True)
            return value
        except Terminal.DoesNotExist:
            raise serializers.ValidationError("Terminal not found or inactive.")

    def validate_customer_id(self, value):
        """Validate that customer exists and belongs to tenant."""
        if value is None:
            return value

        tenant = self.context["request"].user.tenant
        try:
            Customer.objects.get(id=value, tenant=tenant)
            return value
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer not found.")

    def validate_items(self, value):
        """Validate that at least one item is provided."""
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """
        Create sale with items and deduct inventory.

        This method:
        1. Generates unique sale number
        2. Creates sale record
        3. Creates sale items
        4. Deducts inventory with locking
        5. Calculates totals
        6. Updates terminal last_used_at
        """
        request = self.context["request"]
        tenant = request.user.tenant
        user = request.user

        items_data = validated_data.pop("items")
        customer_id = validated_data.pop("customer_id", None)
        terminal_id = validated_data.pop("terminal_id")
        tax_rate = validated_data.pop("tax_rate", Decimal("0.00"))
        discount = validated_data.pop("discount", Decimal("0.00"))

        # Get customer and terminal
        customer = Customer.objects.get(id=customer_id) if customer_id else None
        terminal = Terminal.objects.select_for_update().get(id=terminal_id)

        # Generate sale number
        last_sale = Sale.objects.filter(tenant=tenant).order_by("-created_at").first()
        if last_sale and last_sale.sale_number:
            try:
                last_number = int(last_sale.sale_number.split("-")[-1])
                sale_number = f"SALE-{last_number + 1:08d}"
            except (ValueError, IndexError):
                sale_number = f"SALE-{1:08d}"
        else:
            sale_number = f"SALE-{1:08d}"

        # Calculate subtotal from items
        subtotal = Decimal("0.00")
        sale_items_to_create = []

        # Validate inventory availability first
        for item_data in items_data:
            inventory_item = InventoryItem.objects.select_for_update().get(
                id=item_data["inventory_item_id"], tenant=tenant
            )

            quantity = item_data["quantity"]
            if inventory_item.quantity < quantity:
                raise serializers.ValidationError(
                    f"Insufficient inventory for {inventory_item.name}. "
                    f"Available: {inventory_item.quantity}, Requested: {quantity}"
                )

            # Use provided unit price or current selling price
            unit_price = item_data.get("unit_price") or inventory_item.selling_price
            item_discount = item_data.get("discount", Decimal("0.00"))
            item_subtotal = (unit_price * quantity) - item_discount

            subtotal += item_subtotal

            sale_items_to_create.append(
                {
                    "inventory_item": inventory_item,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount": item_discount,
                    "subtotal": item_subtotal,
                    "notes": item_data.get("notes", ""),
                }
            )

        # Calculate tax and total
        tax = (subtotal * tax_rate) / Decimal("100.00")
        total = subtotal + tax - discount

        # Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            sale_number=sale_number,
            customer=customer,
            branch=terminal.branch,
            terminal=terminal,
            employee=user,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
            **validated_data,
        )

        # Create sale items and deduct inventory
        for item_data in sale_items_to_create:
            inventory_item = item_data.pop("inventory_item")

            # Create sale item
            SaleItem.objects.create(sale=sale, inventory_item=inventory_item, **item_data)

            # Deduct inventory
            inventory_item.quantity -= item_data["quantity"]
            inventory_item.save(update_fields=["quantity", "updated_at"])

        # Update terminal last used
        terminal.mark_as_used()

        # Update customer total purchases if customer exists
        if customer:
            customer.total_purchases += total
            customer.save(update_fields=["total_purchases", "updated_at"])

        return sale


class SaleItemDetailSerializer(serializers.ModelSerializer):
    """Serializer for sale item details."""

    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "inventory_item_sku",
            "quantity",
            "unit_price",
            "discount",
            "subtotal",
            "notes",
        ]


class SaleDetailSerializer(serializers.ModelSerializer):
    """Serializer for sale details."""

    items = SaleItemDetailSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    terminal_name = serializers.CharField(source="terminal.terminal_id", read_only=True)
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "customer",
            "customer_name",
            "branch",
            "branch_name",
            "terminal",
            "terminal_name",
            "employee",
            "employee_name",
            "items",
            "subtotal",
            "tax",
            "discount",
            "total",
            "payment_method",
            "payment_details",
            "status",
            "notes",
            "created_at",
            "completed_at",
        ]


class SaleListSerializer(serializers.ModelSerializer):
    """Serializer for sale list."""

    customer_name = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "customer_name",
            "employee_name",
            "total",
            "payment_method",
            "status",
            "items_count",
            "created_at",
        ]

    def get_customer_name(self, obj):
        """Get customer name or 'Walk-in' if no customer."""
        return obj.customer.get_full_name() if obj.customer else "Walk-in"

    def get_items_count(self, obj):
        """Get count of items in sale."""
        return obj.items.count()


class SaleHoldSerializer(serializers.Serializer):
    """Serializer for putting a sale on hold."""

    notes = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        """Put sale on hold."""
        instance.put_on_hold()
        if validated_data.get("notes"):
            instance.notes = validated_data["notes"]
            instance.save(update_fields=["notes", "updated_at"])
        return instance
