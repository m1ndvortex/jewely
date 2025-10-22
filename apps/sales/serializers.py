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
    - Inventory deduction with select_for_update locking
    - Customer association
    - Payment processing
    - Tax and discount calculation
    - Unique sale number generation
    - Transaction handling with rollback on errors

    Implements Requirement 11: Point of Sale (POS) System
    """

    customer_id = serializers.UUIDField(required=False, allow_null=True)
    terminal_id = serializers.UUIDField()
    items = SaleItemCreateSerializer(many=True)
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHOD_CHOICES)
    payment_details = serializers.JSONField(required=False, default=dict)
    split_payments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="List of split payments: [{'method': 'CASH', 'amount': '50.00'}, {'method': 'CARD', 'amount': '30.00'}]",
    )
    tax_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), required=False
    )
    discount_type = serializers.ChoiceField(
        choices=[("FIXED", "Fixed Amount"), ("PERCENTAGE", "Percentage")],
        default="FIXED",
        required=False,
    )
    discount_value = serializers.DecimalField(
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

    def validate_discount_value(self, value):
        """Validate discount value based on discount type."""
        if value < 0:
            raise serializers.ValidationError("Discount value cannot be negative.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        discount_type = attrs.get("discount_type", "FIXED")
        discount_value = attrs.get("discount_value", Decimal("0.00"))
        payment_method = attrs.get("payment_method")
        split_payments = attrs.get("split_payments", [])

        # Validate percentage discount
        if discount_type == "PERCENTAGE" and discount_value > 100:
            raise serializers.ValidationError(
                {"discount_value": "Percentage discount cannot exceed 100%."}
            )

        # Validate split payments
        if payment_method == "SPLIT":
            if not split_payments:
                raise serializers.ValidationError(
                    {"split_payments": "Split payments are required when payment method is SPLIT."}
                )

            # Validate each split payment
            total_split_amount = Decimal("0.00")
            valid_methods = [
                choice[0] for choice in Sale.PAYMENT_METHOD_CHOICES if choice[0] != "SPLIT"
            ]

            for i, payment in enumerate(split_payments):
                if "method" not in payment or "amount" not in payment:
                    raise serializers.ValidationError(
                        {
                            "split_payments": f"Split payment {i+1} must have 'method' and 'amount' fields."
                        }
                    )

                method = payment["method"]
                if method not in valid_methods:
                    raise serializers.ValidationError(
                        {
                            "split_payments": f"Invalid payment method '{method}' in split payment {i+1}."
                        }
                    )

                try:
                    amount = Decimal(str(payment["amount"]))
                    if amount <= 0:
                        raise serializers.ValidationError(
                            {
                                "split_payments": f"Split payment {i+1} amount must be greater than 0."
                            }
                        )
                    total_split_amount += amount
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        {"split_payments": f"Invalid amount in split payment {i+1}."}
                    )

            # Store total split amount for validation in create method
            attrs["_total_split_amount"] = total_split_amount

        return attrs

    @transaction.atomic
    def create(self, validated_data):  # noqa: C901
        """
        Create sale with items and deduct inventory.

        This method implements comprehensive POS backend logic:
        1. Generates unique sale number with collision handling
        2. Validates inventory availability with select_for_update locking
        3. Creates sale record with proper transaction handling
        4. Creates sale items and deducts inventory atomically
        5. Calculates taxes and discounts accurately
        6. Updates terminal and customer records
        7. Handles errors with proper rollback

        Implements Requirement 11: Complete POS transaction processing
        """
        request = self.context["request"]
        tenant = request.user.tenant
        user = request.user

        try:
            # Extract validated data
            items_data = validated_data.pop("items")
            customer_id = validated_data.pop("customer_id", None)
            terminal_id = validated_data.pop("terminal_id")
            tax_rate = validated_data.pop("tax_rate", Decimal("0.00"))
            discount_type = validated_data.pop("discount_type", "FIXED")
            discount_value = validated_data.pop("discount_value", Decimal("0.00"))
            split_payments = validated_data.pop("split_payments", [])
            total_split_amount = validated_data.pop("_total_split_amount", None)

            # Get customer and terminal with proper locking
            customer = None
            if customer_id:
                try:
                    customer = Customer.objects.select_for_update().get(
                        id=customer_id, tenant=tenant
                    )
                except Customer.DoesNotExist:
                    raise serializers.ValidationError("Customer not found.")

            try:
                terminal = Terminal.objects.select_for_update().get(
                    id=terminal_id, branch__tenant=tenant, is_active=True
                )
            except Terminal.DoesNotExist:
                raise serializers.ValidationError("Terminal not found or inactive.")

            # Generate unique sale number with collision handling
            sale_number = self._generate_unique_sale_number(tenant)

            # Validate inventory and prepare sale items
            subtotal = Decimal("0.00")
            sale_items_to_create = []
            inventory_updates = []

            for item_data in items_data:
                try:
                    inventory_item = InventoryItem.objects.select_for_update().get(
                        id=item_data["inventory_item_id"], tenant=tenant, is_active=True
                    )
                except InventoryItem.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Inventory item {item_data['inventory_item_id']} not found or inactive."
                    )

                quantity = item_data["quantity"]

                # Validate inventory availability
                if inventory_item.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient inventory for '{inventory_item.name}'. "
                        f"Available: {inventory_item.quantity}, Requested: {quantity}"
                    )

                # Validate serialized items (only one can be sold at a time)
                if inventory_item.serial_number and quantity > 1:
                    raise serializers.ValidationError(
                        f"Cannot sell more than 1 unit of serialized item '{inventory_item.name}'."
                    )

                # Use provided unit price or current selling price
                unit_price = item_data.get("unit_price") or inventory_item.selling_price
                if unit_price <= 0:
                    raise serializers.ValidationError(
                        f"Invalid unit price for item '{inventory_item.name}'."
                    )

                item_discount = item_data.get("discount", Decimal("0.00"))
                item_subtotal = (unit_price * quantity) - item_discount

                if item_subtotal < 0:
                    raise serializers.ValidationError(
                        f"Item discount cannot exceed item total for '{inventory_item.name}'."
                    )

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

                inventory_updates.append({"item": inventory_item, "quantity_to_deduct": quantity})

            # Calculate discount amount
            if discount_type == "PERCENTAGE":
                discount_amount = (subtotal * discount_value) / Decimal("100.00")
            else:  # FIXED
                discount_amount = discount_value

            # Validate total discount doesn't exceed subtotal
            if discount_amount > subtotal:
                raise serializers.ValidationError("Total discount cannot exceed subtotal amount.")

            # Calculate tax and total
            discounted_subtotal = subtotal - discount_amount
            tax_amount = (discounted_subtotal * tax_rate) / Decimal("100.00")
            total = discounted_subtotal + tax_amount

            if total < 0:
                raise serializers.ValidationError("Sale total cannot be negative.")

            # Validate split payments total matches sale total
            if validated_data.get("payment_method") == "SPLIT":
                if abs(total_split_amount - total) > Decimal("0.01"):  # Allow 1 cent tolerance
                    raise serializers.ValidationError(
                        f"Split payments total ({total_split_amount}) must equal sale total ({total})."
                    )

                # Store split payment details
                validated_data["payment_details"] = {
                    "split_payments": split_payments,
                    "total_amount": str(total),
                }

            # Create sale record
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number=sale_number,
                customer=customer,
                branch=terminal.branch,
                terminal=terminal,
                employee=user,
                subtotal=subtotal,
                tax=tax_amount,
                discount=discount_amount,
                total=total,
                **validated_data,
            )

            # Create sale items and update inventory atomically
            for item_data in sale_items_to_create:
                inventory_item = item_data.pop("inventory_item")

                # Create sale item
                SaleItem.objects.create(sale=sale, inventory_item=inventory_item, **item_data)

            # Deduct inventory quantities
            for update_data in inventory_updates:
                item = update_data["item"]
                quantity_to_deduct = update_data["quantity_to_deduct"]

                item.quantity -= quantity_to_deduct
                if item.quantity < 0:
                    raise serializers.ValidationError(
                        f"Inventory quantity would become negative for '{item.name}'."
                    )
                item.save(update_fields=["quantity", "updated_at"])

            # Update terminal last used timestamp
            terminal.mark_as_used()

            # Handle store credit payment
            if validated_data.get("payment_method") == "STORE_CREDIT":
                if not customer:
                    raise serializers.ValidationError(
                        "Customer is required for store credit payment."
                    )

                if customer.store_credit < total:
                    raise serializers.ValidationError(
                        f"Insufficient store credit. Available: {customer.store_credit}, Required: {total}"
                    )

                # Deduct store credit
                customer.store_credit -= total

            # Update customer total purchases if customer exists
            if customer:
                customer.total_purchases += total
                customer.save(update_fields=["total_purchases", "store_credit", "updated_at"])

            # Create accounting entries (placeholder for future accounting integration)
            # TODO: Implement accounting entries when accounting system is ready
            # This should create journal entries for:
            # - Debit: Cash/Accounts Receivable (total amount)
            # - Credit: Sales Revenue (subtotal)
            # - Credit: Sales Tax Payable (tax amount)
            # - Debit: Cost of Goods Sold (inventory cost)
            # - Credit: Inventory (inventory cost)

            return sale

        except Exception as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Sale creation failed: {str(e)}", exc_info=True)

            # Re-raise validation errors as-is
            if isinstance(e, serializers.ValidationError):
                raise

            # Convert other exceptions to validation errors
            raise serializers.ValidationError(f"Sale creation failed: {str(e)}")

    def _generate_unique_sale_number(self, tenant):
        """
        Generate a unique sale number with collision handling.

        Format: SALE-YYYYMMDD-NNNNNN
        Where YYYYMMDD is current date and NNNNNN is sequential number.
        """
        import random

        from django.utils import timezone

        today = timezone.now().date()
        date_str = today.strftime("%Y%m%d")

        # Try to get the last sale number for today
        today_sales = Sale.objects.filter(
            tenant=tenant, created_at__date=today, sale_number__startswith=f"SALE-{date_str}-"
        ).order_by("-sale_number")

        if today_sales.exists():
            last_sale = today_sales.first()
            try:
                # Extract the sequential number
                last_number = int(last_sale.sale_number.split("-")[-1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                # Fallback to random number if parsing fails
                next_number = random.randint(1, 999999)
        else:
            next_number = 1

        # Generate sale number with retry logic for collision handling
        max_retries = 10
        for attempt in range(max_retries):
            sale_number = f"SALE-{date_str}-{next_number:06d}"

            # Check if this number already exists
            if not Sale.objects.filter(tenant=tenant, sale_number=sale_number).exists():
                return sale_number

            # If collision, increment and try again
            next_number += 1

        # If all retries failed, use timestamp-based number
        timestamp = int(timezone.now().timestamp() * 1000) % 1000000
        return f"SALE-{date_str}-{timestamp:06d}"


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
