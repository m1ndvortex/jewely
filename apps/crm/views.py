"""
Views for CRM functionality.

Implements Requirement 12: Customer Relationship Management (CRM)
- Customer list view with search and filters
- Customer profile view with purchase history
- Customer create/edit forms
- Customer communication history logging
"""

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from rest_framework import filters, generics, permissions

from apps.core.permissions import HasTenantAccess
from apps.core.tenant_context import set_tenant_context

from .models import (
    Customer,
    CustomerCommunication,
    GiftCard,
    GiftCardTransaction,
    LoyaltyTier,
    LoyaltyTransaction,
)
from .serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerSerializer,
    GiftCardSerializer,
)


class TenantContextMixin:
    """Mixin to set tenant context for API views."""

    def initial(self, request, *args, **kwargs):
        """Set tenant context after authentication."""
        super().initial(request, *args, **kwargs)
        if hasattr(request, "user") and hasattr(request.user, "tenant") and request.user.tenant:
            set_tenant_context(request.user.tenant.id)


# Customer Management Views


@login_required
@require_http_methods(["GET"])
def customer_list(request):
    """
    Customer list view with search and filters.

    Implements Requirement 12.1: Customer list view with search and filters
    Implements Requirement 12.7: Customer segmentation for targeted marketing campaigns

    Features:
    - Search by name, phone, email, customer number
    - Filter by loyalty tier, status, tags
    - Sort by various fields
    - Pagination
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    # Get filter parameters
    search_query = request.GET.get("q", "")
    tier_filter = request.GET.get("tier", "")
    status_filter = request.GET.get("status", "")
    tag_filter = request.GET.get("tag", "")
    sort_by = request.GET.get("sort", "-created_at")

    # Base queryset
    customers = Customer.objects.filter(tenant=request.user.tenant).select_related("loyalty_tier")

    # Apply search
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(customer_number__icontains=search_query)
        )

    # Apply filters
    if tier_filter:
        customers = customers.filter(loyalty_tier_id=tier_filter)

    if status_filter == "active":
        customers = customers.filter(is_active=True)
    elif status_filter == "inactive":
        customers = customers.filter(is_active=False)

    if tag_filter:
        customers = customers.filter(tags__contains=[tag_filter])

    # Apply sorting
    valid_sort_fields = [
        "customer_number",
        "-customer_number",
        "first_name",
        "-first_name",
        "total_purchases",
        "-total_purchases",
        "loyalty_points",
        "-loyalty_points",
        "created_at",
        "-created_at",
        "last_purchase_at",
        "-last_purchase_at",
    ]
    if sort_by in valid_sort_fields:
        customers = customers.order_by(sort_by)

    # Get loyalty tiers for filter dropdown
    loyalty_tiers = LoyaltyTier.objects.filter(tenant=request.user.tenant, is_active=True)

    # Get all unique tags for filter dropdown
    all_tags = set()
    for customer in Customer.objects.filter(tenant=request.user.tenant).only("tags"):
        if customer.tags:
            all_tags.update(customer.tags)

    context = {
        "customers": customers[:100],  # Limit to 100 for initial load
        "search_query": search_query,
        "tier_filter": tier_filter,
        "status_filter": status_filter,
        "tag_filter": tag_filter,
        "sort_by": sort_by,
        "loyalty_tiers": loyalty_tiers,
        "all_tags": sorted(all_tags),
    }

    return render(request, "crm/customer_list.html", context)


@login_required
@require_http_methods(["GET"])
def customer_detail(request, customer_id):
    """
    Customer profile view with purchase history.

    Implements Requirement 12.2: Customer profile view with purchase history
    Implements Requirement 12.6: Track customer communication history

    Features:
    - Customer information
    - Purchase history
    - Loyalty points and tier information
    - Store credit balance
    - Communication history
    - Gift cards
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    customer = get_object_or_404(
        Customer.objects.select_related("loyalty_tier", "referred_by"),
        id=customer_id,
        tenant=request.user.tenant,
    )

    # Get purchase history (from sales app)
    from apps.sales.models import Sale

    purchases = (
        Sale.objects.filter(customer_id=customer_id, tenant=request.user.tenant)
        .select_related("branch", "employee")
        .order_by("-created_at")[:20]
    )

    # Get loyalty transactions
    loyalty_transactions = customer.loyalty_transactions.all()[:20]

    # Get communication history
    communications = customer.communications.select_related("created_by").order_by(
        "-communication_date"
    )[:20]

    # Get gift cards
    gift_cards = GiftCard.objects.filter(
        Q(purchased_by=customer) | Q(recipient=customer), tenant=request.user.tenant
    ).order_by("-created_at")[:10]

    # Get referrals
    referrals = Customer.objects.filter(referred_by=customer, tenant=request.user.tenant)[:10]

    # Calculate statistics
    purchase_stats = {
        "total_count": purchases.count(),
        "total_amount": customer.total_purchases,
        "average_order_value": (
            customer.total_purchases / purchases.count() if purchases.count() > 0 else 0
        ),
    }

    context = {
        "customer": customer,
        "purchases": purchases,
        "loyalty_transactions": loyalty_transactions,
        "communications": communications,
        "gift_cards": gift_cards,
        "referrals": referrals,
        "purchase_stats": purchase_stats,
    }

    return render(request, "crm/customer_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    """
    Customer creation form.

    Implements Requirement 12: Customer create forms
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    if request.method == "POST":
        # Handle form submission via HTMX
        return customer_create_submit(request)

    # Get loyalty tiers for dropdown
    loyalty_tiers = LoyaltyTier.objects.filter(tenant=request.user.tenant, is_active=True)

    context = {
        "loyalty_tiers": loyalty_tiers,
    }

    return render(request, "crm/customer_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def customer_edit(request, customer_id):
    """
    Customer edit form.

    Implements Requirement 12: Customer edit forms
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    if request.method == "POST":
        # Handle form submission via HTMX
        return customer_edit_submit(request, customer_id)

    # Get loyalty tiers for dropdown
    loyalty_tiers = LoyaltyTier.objects.filter(tenant=request.user.tenant, is_active=True)

    context = {
        "customer": customer,
        "loyalty_tiers": loyalty_tiers,
        "is_edit": True,
    }

    return render(request, "crm/customer_form.html", context)


@login_required
@require_http_methods(["POST"])
def customer_create_submit(request):
    """Handle customer creation form submission."""
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        # Generate customer number
        last_customer = (
            Customer.objects.filter(tenant=request.user.tenant).order_by("-customer_number").first()
        )

        if last_customer and last_customer.customer_number.startswith("CUST-"):
            try:
                last_number = int(last_customer.customer_number.split("-")[1])
                customer_number = f"CUST-{last_number + 1:06d}"
            except (IndexError, ValueError):
                customer_number = (
                    f"CUST-{Customer.objects.filter(tenant=request.user.tenant).count() + 1:06d}"
                )
        else:
            customer_number = (
                f"CUST-{Customer.objects.filter(tenant=request.user.tenant).count() + 1:06d}"
            )

        # Create customer
        customer = Customer.objects.create(
            tenant=request.user.tenant,
            customer_number=customer_number,
            first_name=request.POST.get("first_name", "").strip(),
            last_name=request.POST.get("last_name", "").strip(),
            email=request.POST.get("email", "").strip() or None,
            phone=request.POST.get("phone", "").strip(),
            alternate_phone=request.POST.get("alternate_phone", "").strip(),
            date_of_birth=request.POST.get("date_of_birth") or None,
            gender=request.POST.get("gender", ""),
            address_line_1=request.POST.get("address_line_1", "").strip(),
            address_line_2=request.POST.get("address_line_2", "").strip(),
            city=request.POST.get("city", "").strip(),
            state=request.POST.get("state", "").strip(),
            postal_code=request.POST.get("postal_code", "").strip(),
            country=request.POST.get("country", "").strip(),
            preferred_communication=request.POST.get("preferred_communication", "EMAIL"),
            marketing_opt_in=request.POST.get("marketing_opt_in") == "on",
            sms_opt_in=request.POST.get("sms_opt_in") == "on",
            notes=request.POST.get("notes", "").strip(),
        )

        # Handle tags
        tags_input = request.POST.get("tags", "").strip()
        if tags_input:
            customer.tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
            customer.save(update_fields=["tags"])

        return redirect("crm:customer_detail", customer_id=customer.id)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def customer_edit_submit(request, customer_id):
    """Handle customer edit form submission."""
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        # Update customer fields
        customer.first_name = request.POST.get("first_name", "").strip()
        customer.last_name = request.POST.get("last_name", "").strip()
        customer.email = request.POST.get("email", "").strip() or None
        customer.phone = request.POST.get("phone", "").strip()
        customer.alternate_phone = request.POST.get("alternate_phone", "").strip()
        customer.date_of_birth = request.POST.get("date_of_birth") or None
        customer.gender = request.POST.get("gender", "")
        customer.address_line_1 = request.POST.get("address_line_1", "").strip()
        customer.address_line_2 = request.POST.get("address_line_2", "").strip()
        customer.city = request.POST.get("city", "").strip()
        customer.state = request.POST.get("state", "").strip()
        customer.postal_code = request.POST.get("postal_code", "").strip()
        customer.country = request.POST.get("country", "").strip()
        customer.preferred_communication = request.POST.get("preferred_communication", "EMAIL")
        customer.marketing_opt_in = request.POST.get("marketing_opt_in") == "on"
        customer.sms_opt_in = request.POST.get("sms_opt_in") == "on"
        customer.notes = request.POST.get("notes", "").strip()

        # Handle tags
        tags_input = request.POST.get("tags", "").strip()
        if tags_input:
            customer.tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
        else:
            customer.tags = []

        customer.save()

        return redirect("crm:customer_detail", customer_id=customer.id)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def customer_communication_add(request, customer_id):
    """
    Add communication record for a customer.

    Implements Requirement 12.6: Track customer communication history
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        communication = CustomerCommunication.objects.create(
            customer=customer,
            communication_type=request.POST.get("communication_type", "NOTE"),
            direction=request.POST.get("direction", "OUTBOUND"),
            subject=request.POST.get("subject", "").strip(),
            content=request.POST.get("content", "").strip(),
            duration_minutes=request.POST.get("duration_minutes") or None,
            created_by=request.user,
        )

        # Return the communication as HTML fragment for HTMX
        context = {"communication": communication}
        return render(request, "crm/partials/communication_item.html", context)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# API Endpoints for CRM


class CustomerListAPIView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for customer list with search and filters.

    Implements Requirement 12: Customer list with search and filters
    """

    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "phone", "customer_number"]
    ordering_fields = [
        "customer_number",
        "first_name",
        "total_purchases",
        "loyalty_points",
        "created_at",
        "last_purchase_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get customers for the authenticated user's tenant."""
        if not hasattr(self.request.user, "tenant") or not self.request.user.tenant:
            return Customer.objects.none()

        queryset = Customer.objects.filter(tenant=self.request.user.tenant).select_related(
            "loyalty_tier"
        )

        # Apply filters
        tier = self.request.query_params.get("tier")
        if tier:
            queryset = queryset.filter(loyalty_tier_id=tier)

        status_filter = self.request.query_params.get("status")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)

        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag])

        return queryset


class CustomerDetailAPIView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for customer detail.

    Implements Requirement 12: Customer profile view with purchase history
    """

    serializer_class = CustomerDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def get_queryset(self):
        """Get customers for the authenticated user's tenant."""
        if not hasattr(self.request.user, "tenant") or not self.request.user.tenant:
            return Customer.objects.none()

        return Customer.objects.filter(tenant=self.request.user.tenant).select_related(
            "loyalty_tier", "referred_by"
        )


class CustomerCreateAPIView(TenantContextMixin, generics.CreateAPIView):
    """
    API endpoint for customer creation.

    Implements Requirement 12: Customer create forms
    """

    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant and generate customer number."""
        # Generate customer number
        last_customer = (
            Customer.objects.filter(tenant=self.request.user.tenant)
            .order_by("-customer_number")
            .first()
        )

        if last_customer and last_customer.customer_number.startswith("CUST-"):
            try:
                last_number = int(last_customer.customer_number.split("-")[1])
                customer_number = f"CUST-{last_number + 1:06d}"
            except (IndexError, ValueError):
                customer_number = f"CUST-{Customer.objects.filter(tenant=self.request.user.tenant).count() + 1:06d}"
        else:
            customer_number = (
                f"CUST-{Customer.objects.filter(tenant=self.request.user.tenant).count() + 1:06d}"
            )

        serializer.save(tenant=self.request.user.tenant, customer_number=customer_number)


class CustomerUpdateAPIView(TenantContextMixin, generics.UpdateAPIView):
    """
    API endpoint for customer update.

    Implements Requirement 12: Customer edit forms
    """

    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def get_queryset(self):
        """Get customers for the authenticated user's tenant."""
        if not hasattr(self.request.user, "tenant") or not self.request.user.tenant:
            return Customer.objects.none()

        return Customer.objects.filter(tenant=self.request.user.tenant)


# Gift Card API Views


class GiftCardListAPIView(TenantContextMixin, generics.ListAPIView):
    """
    API endpoint for gift card list with search and filters.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card issuance and balance tracking
    """

    serializer_class = GiftCardSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "card_number",
        "purchased_by__first_name",
        "purchased_by__last_name",
        "recipient__first_name",
        "recipient__last_name",
    ]
    ordering_fields = [
        "card_number",
        "initial_value",
        "current_balance",
        "created_at",
        "expires_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get gift cards for the authenticated user's tenant."""
        if not hasattr(self.request.user, "tenant") or not self.request.user.tenant:
            return GiftCard.objects.none()

        queryset = GiftCard.objects.filter(tenant=self.request.user.tenant).select_related(
            "purchased_by", "recipient", "issued_by"
        )

        # Apply filters
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset


class GiftCardDetailAPIView(TenantContextMixin, generics.RetrieveAPIView):
    """
    API endpoint for gift card detail.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Track gift card and credit transactions
    """

    serializer_class = GiftCardSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def get_queryset(self):
        """Get gift cards for the authenticated user's tenant."""
        if not hasattr(self.request.user, "tenant") or not self.request.user.tenant:
            return GiftCard.objects.none()

        return GiftCard.objects.filter(tenant=self.request.user.tenant).select_related(
            "purchased_by", "recipient", "issued_by"
        )


class GiftCardCreateAPIView(TenantContextMixin, generics.CreateAPIView):
    """
    API endpoint for gift card creation.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card issuance and balance tracking
    """

    serializer_class = GiftCardSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantAccess]

    def perform_create(self, serializer):
        """Set tenant and issued_by."""
        serializer.save(tenant=self.request.user.tenant, issued_by=self.request.user)


# Loyalty Program Views


@login_required
@require_http_methods(["GET"])
def loyalty_tier_list(request):
    """
    Loyalty tier configuration interface.

    Implements Requirement 36: Enhanced Loyalty Program
    - Display all loyalty tiers with their benefits
    - Allow creation and editing of tiers
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    tiers = LoyaltyTier.objects.filter(tenant=request.user.tenant).order_by("order", "min_spending")

    context = {
        "tiers": tiers,
    }

    return render(request, "crm/loyalty_tier_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def loyalty_tier_create(request):
    """
    Create a new loyalty tier.

    Implements Requirement 36: Enhanced Loyalty Program
    - Define tier-specific benefits including discount percentages
    - Set spending thresholds for automatic upgrades
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    if request.method == "POST":
        try:
            from decimal import Decimal

            LoyaltyTier.objects.create(
                tenant=request.user.tenant,
                name=request.POST.get("name", "").strip(),
                min_spending=Decimal(request.POST.get("min_spending", "0")),
                discount_percentage=Decimal(request.POST.get("discount_percentage", "0")),
                points_multiplier=Decimal(request.POST.get("points_multiplier", "1.0")),
                validity_months=int(request.POST.get("validity_months", "12")),
                benefits_description=request.POST.get("benefits_description", "").strip(),
                order=int(request.POST.get("order", "0")),
                is_active=request.POST.get("is_active") == "on",
            )

            return redirect("crm:loyalty_tier_list")

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    context = {}
    return render(request, "crm/loyalty_tier_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def loyalty_tier_edit(request, tier_id):
    """
    Edit an existing loyalty tier.

    Implements Requirement 36: Enhanced Loyalty Program
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    tier = get_object_or_404(LoyaltyTier, id=tier_id, tenant=request.user.tenant)

    if request.method == "POST":
        try:
            from decimal import Decimal

            tier.name = request.POST.get("name", "").strip()
            tier.min_spending = Decimal(request.POST.get("min_spending", "0"))
            tier.discount_percentage = Decimal(request.POST.get("discount_percentage", "0"))
            tier.points_multiplier = Decimal(request.POST.get("points_multiplier", "1.0"))
            tier.validity_months = int(request.POST.get("validity_months", "12"))
            tier.benefits_description = request.POST.get("benefits_description", "").strip()
            tier.order = int(request.POST.get("order", "0"))
            tier.is_active = request.POST.get("is_active") == "on"
            tier.save()

            return redirect("crm:loyalty_tier_list")

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    context = {
        "tier": tier,
        "is_edit": True,
    }
    return render(request, "crm/loyalty_tier_form.html", context)


@login_required
@require_http_methods(["POST"])
def loyalty_points_redeem(request, customer_id):
    """
    Redeem loyalty points for a customer.

    Implements Requirement 36: Enhanced Loyalty Program
    - Allow point redemption for discounts, products, or services
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        points = int(request.POST.get("points", 0))
        description = request.POST.get("description", "").strip()

        if points <= 0:
            return JsonResponse({"error": "Points must be greater than 0"}, status=400)

        if points > customer.loyalty_points:
            return JsonResponse({"error": "Insufficient loyalty points"}, status=400)

        # Redeem points
        customer.redeem_loyalty_points(points, description or f"Points redeemed: {points}")

        return JsonResponse(
            {
                "success": True,
                "remaining_points": customer.loyalty_points,
                "message": f"Successfully redeemed {points} points",
            }
        )

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def loyalty_points_adjust(request, customer_id):
    """
    Manually adjust loyalty points for a customer.

    Implements Requirement 36: Enhanced Loyalty Program
    - Allow manual point adjustments by staff
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        points = int(request.POST.get("points", 0))
        description = request.POST.get("description", "").strip()

        if points == 0:
            return JsonResponse({"error": "Points adjustment cannot be 0"}, status=400)

        # Create adjustment transaction
        if points > 0:
            customer.add_loyalty_points(points, description or f"Manual adjustment: +{points}")
        else:
            # For negative adjustments, use redeem but with adjusted transaction type
            abs_points = abs(points)
            if abs_points > customer.loyalty_points:
                return JsonResponse({"error": "Insufficient loyalty points"}, status=400)

            customer.loyalty_points -= abs_points
            customer.save(update_fields=["loyalty_points"])

            LoyaltyTransaction.objects.create(
                customer=customer,
                transaction_type=LoyaltyTransaction.ADJUSTED,
                points=-abs_points,
                description=description or f"Manual adjustment: {points}",
                created_by=request.user,
            )

        return JsonResponse(
            {
                "success": True,
                "current_points": customer.loyalty_points,
                "message": f"Successfully adjusted points by {points}",
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def loyalty_tier_upgrade_check(request, customer_id):
    """
    Check and upgrade customer's loyalty tier based on spending.

    Implements Requirement 36: Enhanced Loyalty Program
    - Automatically upgrade customers based on spending thresholds
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        old_tier = customer.loyalty_tier
        customer.update_loyalty_tier()
        customer.refresh_from_db()
        new_tier = customer.loyalty_tier

        if old_tier != new_tier:
            return JsonResponse(
                {
                    "success": True,
                    "upgraded": True,
                    "old_tier": old_tier.name if old_tier else "None",
                    "new_tier": new_tier.name if new_tier else "None",
                    "message": f"Customer upgraded to {new_tier.name if new_tier else 'None'}",
                }
            )
        else:
            return JsonResponse(
                {
                    "success": True,
                    "upgraded": False,
                    "current_tier": new_tier.name if new_tier else "None",
                    "message": "Customer tier unchanged",
                }
            )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def loyalty_points_transfer(request, customer_id):
    """
    Transfer loyalty points to another customer (family member).

    Implements Requirement 36.9: Allow point transfers between family members
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        recipient_id = request.POST.get("recipient_id")
        points = int(request.POST.get("points", 0))
        description = request.POST.get("description", "").strip()

        if not recipient_id:
            return JsonResponse({"error": "Recipient customer ID is required"}, status=400)

        recipient = get_object_or_404(Customer, id=recipient_id, tenant=request.user.tenant)

        if recipient == customer:
            return JsonResponse({"error": "Cannot transfer points to yourself"}, status=400)

        # Transfer points
        customer.transfer_points_to(recipient, points, description)

        return JsonResponse(
            {
                "success": True,
                "sender_remaining_points": customer.loyalty_points,
                "recipient_new_points": recipient.loyalty_points,
                "message": f"Successfully transferred {points} points to {recipient.get_full_name()}",
            }
        )

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def loyalty_points_expire(request, customer_id):
    """
    Expire old loyalty points for a customer.

    Implements Requirement 36.8: Set point expiration policies to encourage usage
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        expiration_months = int(request.POST.get("expiration_months", 12))
        expired_points = customer.expire_old_points(expiration_months)

        return JsonResponse(
            {
                "success": True,
                "expired_points": expired_points,
                "remaining_points": customer.loyalty_points,
                "message": f"Expired {expired_points} points older than {expiration_months} months",
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def referral_stats(request):
    """
    View referral program performance and ROI.

    Implements Requirement 36.12: Monitor referral program performance and ROI
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    # Get referral statistics
    total_referrals = Customer.objects.filter(
        tenant=request.user.tenant, referred_by__isnull=False
    ).count()

    total_referrers = (
        Customer.objects.filter(tenant=request.user.tenant, referrals__isnull=False)
        .distinct()
        .count()
    )

    # Get top referrers
    from django.db.models import Count

    top_referrers = (
        Customer.objects.filter(tenant=request.user.tenant)
        .annotate(referral_count=Count("referrals"))
        .filter(referral_count__gt=0)
        .order_by("-referral_count")[:10]
    )

    # Calculate referral value (total purchases by referred customers)
    referred_customers = Customer.objects.filter(
        tenant=request.user.tenant, referred_by__isnull=False
    )
    total_referral_value = sum(c.total_purchases for c in referred_customers)

    # Calculate ROI (simplified - rewards given vs value generated)
    # Assuming 100 points per referral = $10 cost
    total_rewards_cost = Decimal(
        str(total_referrals * 150 * 0.10)
    )  # 150 points total (100+50) * $0.10 per point
    roi_percentage = (
        ((total_referral_value - total_rewards_cost) / total_rewards_cost * Decimal("100"))
        if total_rewards_cost > 0
        else Decimal("0")
    )

    context = {
        "total_referrals": total_referrals,
        "total_referrers": total_referrers,
        "top_referrers": top_referrers,
        "total_referral_value": total_referral_value,
        "total_rewards_cost": total_rewards_cost,
        "roi_percentage": roi_percentage,
    }

    return render(request, "crm/referral_stats.html", context)


# Gift Card Management Views


@login_required
@require_http_methods(["GET"])
def gift_card_list(request):
    """
    Gift card list view with search and filters.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card issuance and balance tracking
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    # Get filter parameters
    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")
    sort_by = request.GET.get("sort", "-created_at")

    # Base queryset
    gift_cards = GiftCard.objects.filter(tenant=request.user.tenant).select_related(
        "purchased_by", "recipient", "issued_by"
    )

    # Apply search
    if search_query:
        gift_cards = gift_cards.filter(
            Q(card_number__icontains=search_query)
            | Q(purchased_by__first_name__icontains=search_query)
            | Q(purchased_by__last_name__icontains=search_query)
            | Q(recipient__first_name__icontains=search_query)
            | Q(recipient__last_name__icontains=search_query)
        )

    # Apply filters
    if status_filter:
        gift_cards = gift_cards.filter(status=status_filter)

    # Apply sorting
    valid_sort_fields = [
        "card_number",
        "-card_number",
        "initial_value",
        "-initial_value",
        "current_balance",
        "-current_balance",
        "created_at",
        "-created_at",
        "expires_at",
        "-expires_at",
    ]
    if sort_by in valid_sort_fields:
        gift_cards = gift_cards.order_by(sort_by)

    context = {
        "gift_cards": gift_cards[:100],  # Limit to 100 for initial load
        "search_query": search_query,
        "status_filter": status_filter,
        "sort_by": sort_by,
        "status_choices": GiftCard.STATUS_CHOICES,
    }

    return render(request, "crm/gift_card_list.html", context)


@login_required
@require_http_methods(["GET"])
def gift_card_detail(request, gift_card_id):
    """
    Gift card detail view with transaction history.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Track gift card and credit transactions
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    gift_card = get_object_or_404(
        GiftCard.objects.select_related("purchased_by", "recipient", "issued_by"),
        id=gift_card_id,
        tenant=request.user.tenant,
    )

    # Get transaction history
    transactions = gift_card.transactions.select_related("created_by", "sale").order_by(
        "-created_at"
    )

    context = {
        "gift_card": gift_card,
        "transactions": transactions,
    }

    return render(request, "crm/gift_card_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def gift_card_create(request):
    """
    Gift card creation form.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card issuance and balance tracking
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    if request.method == "POST":
        return gift_card_create_submit(request)

    # Get customers for dropdown
    customers = Customer.objects.filter(tenant=request.user.tenant, is_active=True).order_by(
        "first_name", "last_name"
    )

    context = {
        "customers": customers,
    }

    return render(request, "crm/gift_card_form.html", context)


@login_required
@require_http_methods(["POST"])
def gift_card_create_submit(request):
    """Handle gift card creation form submission."""
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        from datetime import datetime
        from decimal import Decimal

        # Get form data
        initial_value = Decimal(request.POST.get("initial_value", "0"))
        purchased_by_id = request.POST.get("purchased_by") or None
        recipient_id = request.POST.get("recipient") or None
        message = request.POST.get("message", "").strip()
        expires_at = request.POST.get("expires_at") or None

        if initial_value <= 0:
            return JsonResponse({"error": "Initial value must be greater than 0"}, status=400)

        # Validate customers belong to tenant
        purchased_by = None
        if purchased_by_id:
            purchased_by = get_object_or_404(
                Customer, id=purchased_by_id, tenant=request.user.tenant
            )

        recipient = None
        if recipient_id:
            recipient = get_object_or_404(Customer, id=recipient_id, tenant=request.user.tenant)

        # Parse expiration date
        expires_at_parsed = None
        if expires_at:
            expires_at_parsed = datetime.strptime(expires_at, "%Y-%m-%d").date()

        # Create gift card
        gift_card = GiftCard.objects.create(
            tenant=request.user.tenant,
            initial_value=initial_value,
            purchased_by=purchased_by,
            recipient=recipient,
            message=message,
            expires_at=expires_at_parsed,
            issued_by=request.user,
        )

        return redirect("crm:gift_card_detail", gift_card_id=gift_card.id)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def gift_card_redeem(request, gift_card_id):
    """
    Redeem gift card balance.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card redemption
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    gift_card = get_object_or_404(GiftCard, id=gift_card_id, tenant=request.user.tenant)

    try:
        from decimal import Decimal

        amount = Decimal(request.POST.get("amount", "0"))
        description = request.POST.get("description", "").strip()

        if amount <= 0:
            return JsonResponse({"error": "Amount must be greater than 0"}, status=400)

        # Use gift card balance
        gift_card.use_balance(
            amount=amount,
            description=description or f"Manual redemption: ${amount}",
            created_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "remaining_balance": str(gift_card.current_balance),
                "status": gift_card.status,
                "message": f"Successfully redeemed ${amount}",
            }
        )

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def gift_card_cancel(request, gift_card_id):
    """
    Cancel a gift card.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card management
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    gift_card = get_object_or_404(GiftCard, id=gift_card_id, tenant=request.user.tenant)

    try:
        reason = request.POST.get("reason", "").strip()

        if gift_card.status != GiftCard.ACTIVE:
            return JsonResponse({"error": "Only active gift cards can be cancelled"}, status=400)

        # Update status
        gift_card.status = GiftCard.CANCELLED
        gift_card.save(update_fields=["status", "updated_at"])

        # Create transaction record
        GiftCardTransaction.objects.create(
            gift_card=gift_card,
            customer=gift_card.recipient or gift_card.purchased_by,
            transaction_type=GiftCardTransaction.CANCELLED,
            amount=gift_card.current_balance,
            description=reason or "Gift card cancelled",
            previous_balance=gift_card.current_balance,
            new_balance=gift_card.current_balance,
            created_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "status": gift_card.status,
                "message": "Gift card cancelled successfully",
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Store Credit Management Views


@login_required
@require_http_methods(["POST"])
def store_credit_add(request, customer_id):
    """
    Add store credit to customer account.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Manage customer store credit balances with transaction history
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        from decimal import Decimal

        amount = Decimal(request.POST.get("amount", "0"))
        description = request.POST.get("description", "").strip()

        if amount <= 0:
            return JsonResponse({"error": "Amount must be greater than 0"}, status=400)

        # Add store credit
        customer.add_store_credit(
            amount=amount,
            description=description or f"Store credit added: ${amount}",
            created_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "new_balance": str(customer.store_credit),
                "message": f"Successfully added ${amount} store credit",
            }
        )

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def store_credit_use(request, customer_id):
    """
    Use store credit from customer account.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Manage customer store credit balances with transaction history
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    try:
        from decimal import Decimal

        amount = Decimal(request.POST.get("amount", "0"))
        description = request.POST.get("description", "").strip()

        if amount <= 0:
            return JsonResponse({"error": "Amount must be greater than 0"}, status=400)

        # Use store credit
        customer.use_store_credit(
            amount=amount,
            description=description or f"Store credit used: ${amount}",
            created_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "new_balance": str(customer.store_credit),
                "message": f"Successfully used ${amount} store credit",
            }
        )

    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def store_credit_transactions(request, customer_id):
    """
    View store credit transaction history for a customer.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Track gift card and credit transactions
    """
    if not hasattr(request.user, "tenant") or not request.user.tenant:
        return redirect("/accounts/login/")

    customer = get_object_or_404(Customer, id=customer_id, tenant=request.user.tenant)

    # Get store credit transactions
    transactions = (
        GiftCardTransaction.objects.filter(
            customer=customer,
            transaction_type__in=[
                GiftCardTransaction.STORE_CREDIT_ADDED,
                GiftCardTransaction.STORE_CREDIT_USED,
                GiftCardTransaction.STORE_CREDIT_REFUNDED,
            ],
        )
        .select_related("created_by", "sale")
        .order_by("-created_at")
    )

    context = {
        "customer": customer,
        "transactions": transactions,
    }

    return render(request, "crm/store_credit_transactions.html", context)
