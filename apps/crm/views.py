"""
Views for CRM functionality.

Implements Requirement 12: Customer Relationship Management (CRM)
- Customer list view with search and filters
- Customer profile view with purchase history
- Customer create/edit forms
- Customer communication history logging
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from rest_framework import filters, generics, permissions

from apps.core.permissions import HasTenantAccess
from apps.core.tenant_context import set_tenant_context

from .models import Customer, CustomerCommunication, GiftCard, LoyaltyTier
from .serializers import CustomerDetailSerializer, CustomerListSerializer, CustomerSerializer


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
