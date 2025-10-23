"""
Services for repair order management.

This module contains business logic and services for repair orders,
including notification handling, status updates, and custom order pricing.
"""

from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone


def send_repair_status_notification(repair_order):
    """
    Send notification to customer about repair order status change.

    This is a placeholder implementation that will be enhanced
    when the full notification system is implemented in task 13.

    Args:
        repair_order: RepairOrder instance
    """
    try:
        # Get customer email
        if not repair_order.customer.email:
            return False

        # Prepare email content based on status
        status_messages = {
            "received": "Your repair order has been received and is being reviewed.",
            "in_progress": "Work has started on your repair order.",
            "quality_check": "Your repair is undergoing quality inspection.",
            "completed": "Your repair has been completed and is ready for pickup.",
            "delivered": "Your repair order has been delivered. Thank you for your business!",
            "cancelled": "Your repair order has been cancelled. Please contact us for more information.",
        }

        subject = f"Repair Order Update - {repair_order.order_number}"
        message = status_messages.get(
            repair_order.status, "Your repair order status has been updated."
        )

        # Email context for future template rendering
        # context = {
        #     "repair_order": repair_order,
        #     "customer": repair_order.customer,
        #     "status_message": message,
        #     "shop_name": repair_order.tenant.company_name,
        # }

        # Render email template (placeholder - will be enhanced later)
        email_body = f"""
Dear {repair_order.customer.first_name},

{message}

Order Details:
- Order Number: {repair_order.order_number}
- Item: {repair_order.item_description}
- Service: {repair_order.get_service_type_display()}
- Status: {repair_order.get_status_display()}

Thank you for choosing {repair_order.tenant.company_name}.

Best regards,
{repair_order.tenant.company_name} Team
        """

        # Send email (if email backend is configured)
        if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[repair_order.customer.email],
                fail_silently=True,  # Don't break the flow if email fails
            )

        return True

    except Exception as e:
        # Log the error (in a real implementation, use proper logging)
        print(f"Failed to send notification for repair order {repair_order.order_number}: {e}")
        return False


def send_work_order_notification(repair_orders, craftsman, notes=None):
    """
    Send notification to craftsman about new work order assignment.

    Args:
        repair_orders: QuerySet of RepairOrder instances
        craftsman: User instance (craftsman)
        notes: Optional notes for the craftsman
    """
    try:
        if not craftsman.email:
            return False

        subject = f'New Work Order Assignment - {timezone.now().strftime("%Y-%m-%d")}'

        # Create email body
        order_list = "\n".join(
            [
                f"- {order.order_number}: {order.item_description} ({order.get_service_type_display()})"
                for order in repair_orders
            ]
        )

        email_body = f"""
Dear {craftsman.get_full_name()},

You have been assigned new repair orders:

{order_list}

{f"Special Instructions: {notes}" if notes else ""}

Please review the work order details and begin work as scheduled.

Best regards,
Management Team
        """

        # Send email (if email backend is configured)
        if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[craftsman.email],
                fail_silently=True,
            )

        return True

    except Exception as e:
        print(f"Failed to send work order notification to {craftsman.get_full_name()}: {e}")
        return False


class CustomOrderPricingCalculator:
    """
    Service for calculating pricing for custom orders based on materials, labor, overhead, and profit margin.

    This service implements the pricing calculator functionality required by task 8.3.
    """

    # Default complexity multipliers for labor cost calculation
    COMPLEXITY_LABOR_MULTIPLIERS = {
        "SIMPLE": Decimal("50.00"),
        "MODERATE": Decimal("100.00"),
        "COMPLEX": Decimal("200.00"),
        "VERY_COMPLEX": Decimal("400.00"),
    }

    def __init__(self, custom_order):
        """
        Initialize the pricing calculator for a custom order.

        Args:
            custom_order: CustomOrder instance
        """
        self.custom_order = custom_order

    def calculate_material_cost(self):
        """
        Calculate total material cost from material requirements.

        Returns:
            Decimal: Total material cost
        """
        total_cost = Decimal("0.00")
        for requirement in self.custom_order.material_requirements.all():
            total_cost += requirement.total_cost
        return total_cost

    def calculate_labor_cost(self, hours=None, hourly_rate=None):
        """
        Calculate labor cost based on complexity or provided hours and rate.

        Args:
            hours: Optional number of hours (overrides complexity-based calculation)
            hourly_rate: Optional hourly rate (default: $50/hour)

        Returns:
            Decimal: Labor cost
        """
        if hours is not None and hourly_rate is not None:
            return Decimal(str(hours)) * Decimal(str(hourly_rate))

        if hours is not None:
            # Use default hourly rate of $50
            return Decimal(str(hours)) * Decimal("50.00")

        # Use complexity-based calculation
        return self.COMPLEXITY_LABOR_MULTIPLIERS.get(
            self.custom_order.complexity, Decimal("100.00")
        )

    def calculate_full_pricing(self, labor_hours=None, hourly_rate=None):
        """
        Calculate complete pricing breakdown for the custom order.

        Args:
            labor_hours: Optional number of labor hours
            hourly_rate: Optional hourly rate

        Returns:
            dict: Complete pricing breakdown
        """
        # Calculate base costs
        material_cost = self.calculate_material_cost()
        labor_cost = self.calculate_labor_cost(labor_hours, hourly_rate)
        base_cost = material_cost + labor_cost

        # Calculate overhead
        overhead_percentage = self.custom_order.overhead_percentage
        overhead_amount = base_cost * (overhead_percentage / 100)
        cost_with_overhead = base_cost + overhead_amount

        # Calculate profit margin
        profit_margin_percentage = self.custom_order.profit_margin_percentage
        profit_amount = cost_with_overhead * (profit_margin_percentage / 100)
        final_price = cost_with_overhead + profit_amount

        return {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "base_cost": base_cost,
            "overhead_percentage": overhead_percentage,
            "overhead_amount": overhead_amount,
            "cost_with_overhead": cost_with_overhead,
            "profit_margin_percentage": profit_margin_percentage,
            "profit_amount": profit_amount,
            "final_price": final_price,
            "breakdown": {
                "materials": material_cost,
                "labor": labor_cost,
                "overhead": overhead_amount,
                "profit": profit_amount,
                "total": final_price,
            },
        }

    def update_order_pricing(self, labor_hours=None, hourly_rate=None):
        """
        Update the custom order with calculated pricing.

        Args:
            labor_hours: Optional number of labor hours
            hourly_rate: Optional hourly rate

        Returns:
            dict: Pricing breakdown
        """
        pricing = self.calculate_full_pricing(labor_hours, hourly_rate)

        # Update the order
        self.custom_order.material_cost = pricing["material_cost"]
        self.custom_order.labor_cost = pricing["labor_cost"]
        self.custom_order.quoted_price = pricing["final_price"]
        self.custom_order.save(
            update_fields=["material_cost", "labor_cost", "quoted_price", "updated_at"]
        )

        return pricing


class CustomOrderInventoryService:
    """
    Service for linking completed custom orders to inventory.

    This service implements the inventory linking functionality required by task 8.3.
    """

    @staticmethod
    def create_inventory_from_custom_order(custom_order, branch, sku=None, user=None):
        """
        Create an inventory item from a completed custom order.

        Args:
            custom_order: CustomOrder instance (must be completed)
            branch: Branch where the item will be stored
            sku: Optional SKU, will be auto-generated if not provided
            user: User creating the inventory item

        Returns:
            InventoryItem: The created inventory item

        Raises:
            ValueError: If order is not completed or inventory item already exists
        """
        from apps.inventory.models import InventoryItem, ProductCategory

        if custom_order.status != "completed":
            raise ValueError("Can only create inventory from completed custom orders")

        if custom_order.created_inventory_item:
            raise ValueError("Inventory item already created for this custom order")

        with transaction.atomic():
            # Generate SKU if not provided
            if not sku:
                sku = f"CUSTOM-{custom_order.order_number}"

            # Get or create a "Custom Orders" category
            category, _ = ProductCategory.objects.get_or_create(
                tenant=custom_order.tenant,
                name="Custom Orders",
                defaults={
                    "description": "Items created from custom orders",
                    "is_active": True,
                },
            )

            # Extract specifications for inventory item
            specs = custom_order.design_specifications or {}
            karat = specs.get("karat", 18)  # Default to 18K
            weight = Decimal(str(specs.get("weight_grams", "10.0")))  # Default weight

            # Create inventory item
            inventory_item = InventoryItem.objects.create(
                tenant=custom_order.tenant,
                sku=sku,
                name=f"Custom: {custom_order.design_description[:100]}",
                category=category,
                description=f"Custom order {custom_order.order_number}: {custom_order.design_description}",
                karat=karat,
                weight_grams=weight,
                craftsmanship_level="HANDMADE",  # Custom orders are typically handmade
                cost_price=custom_order.material_cost + custom_order.labor_cost,
                selling_price=custom_order.final_price or custom_order.quoted_price,
                quantity=1,  # Custom orders typically produce one item
                branch=branch,
                serial_number=f"CUSTOM-{custom_order.order_number}",
                notes=f"Created from custom order {custom_order.order_number}",
                is_active=True,
            )

            # Link the inventory item to the custom order
            custom_order.created_inventory_item = inventory_item
            custom_order.save(update_fields=["created_inventory_item", "updated_at"])

            return inventory_item

    @staticmethod
    def source_materials_from_inventory(custom_order, user):
        """
        Source materials for a custom order from existing inventory where possible.

        Args:
            custom_order: CustomOrder instance
            user: User performing the action

        Returns:
            dict: Summary of sourcing results
        """
        from apps.inventory.models import InventoryItem

        results = {"sourced": [], "not_found": [], "insufficient": [], "errors": []}

        with transaction.atomic():
            for requirement in custom_order.material_requirements.filter(is_acquired=False):
                try:
                    # Try to find matching inventory items
                    # This is a simple matching - in a real system you might want more sophisticated matching
                    matching_items = InventoryItem.objects.filter(
                        tenant=custom_order.tenant,
                        name__icontains=requirement.material_name,
                        is_active=True,
                        quantity__gt=0,
                    ).order_by("-quantity")

                    if not matching_items.exists():
                        results["not_found"].append(
                            {
                                "requirement": requirement,
                                "message": f"No inventory found for {requirement.material_name}",
                            }
                        )
                        continue

                    # Try to source from the first matching item with sufficient quantity
                    sourced = False
                    for item in matching_items:
                        if requirement.can_source_from_inventory(item):
                            requirement.source_from_inventory(item)
                            results["sourced"].append(
                                {
                                    "requirement": requirement,
                                    "inventory_item": item,
                                    "message": f"Sourced {requirement.quantity_required} {requirement.unit} from {item.sku}",
                                }
                            )
                            sourced = True
                            break

                    if not sourced:
                        results["insufficient"].append(
                            {
                                "requirement": requirement,
                                "message": f"Insufficient inventory for {requirement.material_name}",
                            }
                        )

                except Exception as e:
                    results["errors"].append({"requirement": requirement, "error": str(e)})

        return results


def send_custom_order_status_notification(custom_order):
    """
    Send notification to customer about custom order status change.

    This implements requirement 13.4: Send notifications to customers when order status changes.

    Args:
        custom_order: CustomOrder instance
    """
    try:
        # Get customer email
        if not custom_order.customer.email:
            return False

        # Prepare email content based on status
        status_messages = {
            "quote_requested": "We have received your custom order request and are preparing a quote.",
            "quote_provided": "Your custom order quote is ready for review.",
            "approved": "Thank you for approving the quote. We will begin designing your custom piece.",
            "in_design": "Our designers are working on your custom piece.",
            "design_approved": "Your design has been approved and we will begin production.",
            "in_production": "Your custom piece is now in production.",
            "quality_check": "Your custom piece is undergoing final quality inspection.",
            "completed": "Your custom order has been completed and is ready for pickup.",
            "delivered": "Your custom order has been delivered. Thank you for your business!",
            "cancelled": "Your custom order has been cancelled. Please contact us for more information.",
        }

        subject = f"Custom Order Update - {custom_order.order_number}"
        message = status_messages.get(
            custom_order.status, "Your custom order status has been updated."
        )

        # Email context for future template rendering
        email_body = f"""
Dear {custom_order.customer.first_name},

{message}

Order Details:
- Order Number: {custom_order.order_number}
- Design: {custom_order.design_description}
- Status: {custom_order.get_status_display()}
- Estimated Completion: {custom_order.estimated_completion or 'TBD'}

Thank you for choosing {custom_order.tenant.company_name}.

Best regards,
{custom_order.tenant.company_name} Team
        """

        # Send email (if email backend is configured)
        if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[custom_order.customer.email],
                fail_silently=True,  # Don't break the flow if email fails
            )

        return True

    except Exception as e:
        # Log the error (in a real implementation, use proper logging)
        print(f"Failed to send notification for custom order {custom_order.order_number}: {e}")
        return False


class WorkOrderGenerator:
    """
    Service for generating work orders for craftsmen with detailed instructions.

    This implements requirement 13.8: Generate work orders for craftsmen with detailed instructions.
    """

    @staticmethod
    def generate_work_order(custom_order, craftsman=None, notes=None):
        """
        Generate a work order for a custom order.

        Args:
            custom_order: CustomOrder instance
            craftsman: User instance (craftsman to assign)
            notes: Optional additional notes for the craftsman

        Returns:
            dict: Work order details
        """
        # Assign craftsman if provided
        if craftsman:
            custom_order.craftsman = craftsman
            custom_order.save(update_fields=["craftsman", "updated_at"])

        # Generate work order content
        work_order = {
            "order_number": custom_order.order_number,
            "customer_name": f"{custom_order.customer.first_name} {custom_order.customer.last_name}",
            "design_description": custom_order.design_description,
            "design_specifications": custom_order.design_specifications,
            "complexity": custom_order.get_complexity_display(),
            "estimated_completion": custom_order.estimated_completion,
            "assigned_craftsman": (
                custom_order.craftsman.get_full_name() if custom_order.craftsman else "Unassigned"
            ),
            "designer": (
                custom_order.designer.get_full_name() if custom_order.designer else "Unassigned"
            ),
            "material_requirements": [],
            "instructions": [],
            "notes": notes or "",
            "created_at": timezone.now(),
        }

        # Add material requirements
        for requirement in custom_order.material_requirements.all():
            work_order["material_requirements"].append(
                {
                    "material_name": requirement.material_name,
                    "material_type": requirement.get_material_type_display(),
                    "quantity": f"{requirement.quantity_required} {requirement.unit}",
                    "specifications": requirement.specifications,
                    "status": "Acquired" if requirement.is_acquired else "Pending",
                    "supplier": requirement.supplier_info or "TBD",
                }
            )

        # Generate detailed instructions based on design specifications
        instructions = WorkOrderGenerator._generate_instructions(custom_order)
        work_order["instructions"] = instructions

        return work_order

    @staticmethod
    def _generate_instructions(custom_order):
        """
        Generate detailed crafting instructions based on design specifications.

        Args:
            custom_order: CustomOrder instance

        Returns:
            list: List of instruction steps
        """
        instructions = []
        specs = custom_order.design_specifications or {}

        # Basic setup instructions
        instructions.append("1. Review all design specifications and material requirements")
        instructions.append("2. Verify all materials are available and meet quality standards")
        instructions.append("3. Prepare workspace and tools according to safety protocols")

        # Material-specific instructions
        if specs.get("karat"):
            instructions.append(f"4. Use {specs['karat']}K gold as specified")

        if specs.get("weight_grams"):
            instructions.append(f"5. Target weight: {specs['weight_grams']} grams")

        if specs.get("stone_type"):
            instructions.append(f"6. Set {specs['stone_type']} stone as per design")

        if specs.get("stone_size"):
            instructions.append(f"7. Stone size: {specs['stone_size']}")

        # Complexity-based instructions
        if custom_order.complexity == "SIMPLE":
            instructions.append("8. Follow standard crafting procedures")
        elif custom_order.complexity == "MODERATE":
            instructions.append("8. Pay attention to detail and finish quality")
        elif custom_order.complexity == "COMPLEX":
            instructions.append(
                "8. Requires advanced techniques - consult senior craftsman if needed"
            )
        elif custom_order.complexity == "VERY_COMPLEX":
            instructions.append("8. Master-level work required - coordinate with design team")

        # Quality control instructions
        instructions.append("9. Perform quality check at each major milestone")
        instructions.append("10. Document progress with photos")
        instructions.append("11. Final inspection before marking as completed")
        instructions.append("12. Clean and polish to final finish standards")

        return instructions

    @staticmethod
    def send_work_order_to_craftsman(work_order, custom_order):
        """
        Send work order notification to assigned craftsman.

        Args:
            work_order: Work order dictionary
            custom_order: CustomOrder instance
        """
        if not custom_order.craftsman or not custom_order.craftsman.email:
            return False

        try:
            subject = f"New Work Order Assignment - {custom_order.order_number}"

            # Format material requirements
            materials_text = "\n".join(
                [
                    f"- {mat['material_name']} ({mat['material_type']}): {mat['quantity']} - {mat['status']}"
                    for mat in work_order["material_requirements"]
                ]
            )

            # Format instructions
            instructions_text = "\n".join(work_order["instructions"])

            email_body = f"""
Dear {custom_order.craftsman.get_full_name()},

You have been assigned a new custom order work order:

ORDER DETAILS:
- Order Number: {work_order['order_number']}
- Customer: {work_order['customer_name']}
- Complexity: {work_order['complexity']}
- Estimated Completion: {work_order['estimated_completion'] or 'TBD'}

DESIGN DESCRIPTION:
{work_order['design_description']}

MATERIAL REQUIREMENTS:
{materials_text}

CRAFTING INSTRUCTIONS:
{instructions_text}

ADDITIONAL NOTES:
{work_order['notes']}

Please review the work order details and begin work as scheduled.

Best regards,
Management Team
            """

            # Send email (if email backend is configured)
            if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
                send_mail(
                    subject=subject,
                    message=email_body,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                    recipient_list=[custom_order.craftsman.email],
                    fail_silently=True,
                )

            return True

        except Exception as e:
            print(f"Failed to send work order to craftsman: {e}")
            return False


def send_overdue_order_reminders():  # noqa: C901
    """
    Send reminders for overdue repair and custom orders.

    This implements requirement 13.5: Send reminders for overdue orders.
    This function should be called by a Celery periodic task.

    Returns:
        dict: Summary of reminders sent
    """
    from django.utils import timezone

    from .models import CustomOrder, RepairOrder

    today = timezone.now().date()
    results = {"repair_orders_reminded": 0, "custom_orders_reminded": 0, "errors": []}

    try:
        # Find overdue repair orders
        overdue_repairs = RepairOrder.objects.filter(
            estimated_completion__lt=today, status__in=["received", "in_progress", "quality_check"]
        ).select_related("customer", "tenant")

        for repair_order in overdue_repairs:
            try:
                if repair_order.customer.email:
                    subject = f"Overdue Repair Order Reminder - {repair_order.order_number}"
                    days_overdue = (today - repair_order.estimated_completion).days

                    message = f"""
Dear {repair_order.customer.first_name},

This is a reminder that your repair order is overdue:

Order Details:
- Order Number: {repair_order.order_number}
- Item: {repair_order.item_description}
- Service: {repair_order.get_service_type_display()}
- Original Due Date: {repair_order.estimated_completion}
- Days Overdue: {days_overdue}

We apologize for the delay and are working to complete your repair as soon as possible.

Please contact us if you have any questions.

Best regards,
{repair_order.tenant.company_name} Team
                    """

                    if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=getattr(
                                settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"
                            ),
                            recipient_list=[repair_order.customer.email],
                            fail_silently=True,
                        )
                        results["repair_orders_reminded"] += 1

            except Exception as e:
                results["errors"].append(
                    f"Failed to send reminder for repair order {repair_order.order_number}: {e}"
                )

        # Find overdue custom orders
        overdue_custom_orders = CustomOrder.objects.filter(
            estimated_completion__lt=today,
            status__in=[
                "approved",
                "in_design",
                "design_approved",
                "in_production",
                "quality_check",
            ],
        ).select_related("customer", "tenant")

        for custom_order in overdue_custom_orders:
            try:
                if custom_order.customer.email:
                    subject = f"Overdue Custom Order Reminder - {custom_order.order_number}"
                    days_overdue = (today - custom_order.estimated_completion).days

                    message = f"""
Dear {custom_order.customer.first_name},

This is a reminder that your custom order is overdue:

Order Details:
- Order Number: {custom_order.order_number}
- Design: {custom_order.design_description}
- Status: {custom_order.get_status_display()}
- Original Due Date: {custom_order.estimated_completion}
- Days Overdue: {days_overdue}

We apologize for the delay and are working to complete your custom piece as soon as possible.

Please contact us if you have any questions.

Best regards,
{custom_order.tenant.company_name} Team
                    """

                    if hasattr(settings, "EMAIL_BACKEND") and settings.EMAIL_BACKEND:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=getattr(
                                settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"
                            ),
                            recipient_list=[custom_order.customer.email],
                            fail_silently=True,
                        )
                        results["custom_orders_reminded"] += 1

            except Exception as e:
                results["errors"].append(
                    f"Failed to send reminder for custom order {custom_order.order_number}: {e}"
                )

        return results

    except Exception as e:
        results["errors"].append(f"General error in overdue reminders: {e}")
        return results
