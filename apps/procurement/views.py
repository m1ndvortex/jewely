"""
Views for procurement management.

This module contains views for supplier management including CRUD operations,
communication tracking, and document management.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.decorators import tenant_required
from apps.core.mixins import TenantMixin

from .forms import SupplierCommunicationForm, SupplierDocumentForm
from .models import Supplier, SupplierCommunication, SupplierDocument


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierListView(TenantMixin, ListView):
    """List view for suppliers with search and filtering."""

    model = Supplier
    template_name = "procurement/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 20

    def get_queryset(self):
        """Filter suppliers by tenant and search query."""
        queryset = Supplier.objects.filter(tenant=self.request.user.tenant)

        # Search functionality
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(contact_person__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone__icontains=search_query)
            )

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)

        # Filter by rating
        rating_filter = self.request.GET.get("rating")
        if rating_filter:
            try:
                rating = int(rating_filter)
                queryset = queryset.filter(rating__gte=rating)
            except ValueError:
                pass

        # Annotate with statistics
        queryset = queryset.annotate(
            total_orders=Count("purchase_orders"), avg_rating=Avg("rating")
        ).select_related("created_by")

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add search parameters to context."""
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["rating_filter"] = self.request.GET.get("rating", "")
        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierDetailView(TenantMixin, DetailView):
    """Detail view for supplier with communications and documents."""

    model = Supplier
    template_name = "procurement/supplier_detail.html"
    context_object_name = "supplier"

    def get_queryset(self):
        """Filter by tenant."""
        return Supplier.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        """Add related data to context."""
        context = super().get_context_data(**kwargs)
        supplier = self.object

        # Recent communications
        context["recent_communications"] = supplier.communications.select_related("created_by")[:5]

        # Recent documents
        context["recent_documents"] = supplier.documents.select_related("uploaded_by")[:5]

        # Statistics
        context["total_orders"] = supplier.purchase_orders.count()
        context["total_order_value"] = supplier.get_total_order_value()
        context["avg_delivery_time"] = supplier.get_average_delivery_time()

        # Pending follow-ups
        context["pending_followups"] = supplier.communications.filter(
            requires_followup=True, is_completed=False
        ).count()

        # Expiring documents
        context["expiring_documents"] = (
            supplier.documents.filter(is_active=True, expiry_date__isnull=False)
            .extra(where=["expiry_date <= CURRENT_DATE + INTERVAL '30 days'"])
            .count()
        )

        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierCreateView(TenantMixin, CreateView):
    """Create view for suppliers."""

    model = Supplier
    template_name = "procurement/supplier_form.html"
    fields = [
        "name",
        "contact_person",
        "email",
        "phone",
        "address",
        "tax_id",
        "payment_terms",
        "rating",
        "notes",
    ]

    def form_valid(self, form):
        """Set tenant and created_by before saving."""
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Supplier '{form.instance.name}' created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to supplier detail page."""
        return reverse("procurement:supplier_detail", kwargs={"pk": self.object.pk})


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierUpdateView(TenantMixin, UpdateView):
    """Update view for suppliers."""

    model = Supplier
    template_name = "procurement/supplier_form.html"
    fields = [
        "name",
        "contact_person",
        "email",
        "phone",
        "address",
        "tax_id",
        "payment_terms",
        "rating",
        "is_active",
        "notes",
    ]

    def get_queryset(self):
        """Filter by tenant."""
        return Supplier.objects.filter(tenant=self.request.user.tenant)

    def form_valid(self, form):
        """Show success message."""
        messages.success(self.request, f"Supplier '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to supplier detail page."""
        return reverse("procurement:supplier_detail", kwargs={"pk": self.object.pk})


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierDeleteView(TenantMixin, DeleteView):
    """Delete view for suppliers."""

    model = Supplier
    template_name = "procurement/supplier_confirm_delete.html"
    success_url = reverse_lazy("procurement:supplier_list")

    def get_queryset(self):
        """Filter by tenant."""
        return Supplier.objects.filter(tenant=self.request.user.tenant)

    def delete(self, request, *args, **kwargs):
        """Show success message on delete."""
        supplier = self.get_object()
        messages.success(request, f"Supplier '{supplier.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierCommunicationCreateView(TenantMixin, CreateView):
    """Create view for supplier communications."""

    model = SupplierCommunication
    form_class = SupplierCommunicationForm
    template_name = "procurement/communication_form.html"

    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        """Add supplier to context."""
        context = super().get_context_data(**kwargs)
        context["supplier"] = get_object_or_404(
            Supplier, pk=self.kwargs["supplier_pk"], tenant=self.request.user.tenant
        )
        return context

    def form_valid(self, form):
        """Set supplier and created_by before saving."""
        supplier = get_object_or_404(
            Supplier, pk=self.kwargs["supplier_pk"], tenant=self.request.user.tenant
        )
        form.instance.supplier = supplier
        form.instance.created_by = self.request.user
        messages.success(self.request, "Communication record created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to supplier detail page."""
        return reverse("procurement:supplier_detail", kwargs={"pk": self.kwargs["supplier_pk"]})


@method_decorator([login_required, tenant_required], name="dispatch")
class SupplierDocumentCreateView(TenantMixin, CreateView):
    """Create view for supplier documents."""

    model = SupplierDocument
    form_class = SupplierDocumentForm
    template_name = "procurement/document_form.html"

    def get_context_data(self, **kwargs):
        """Add supplier to context."""
        context = super().get_context_data(**kwargs)
        context["supplier"] = get_object_or_404(
            Supplier, pk=self.kwargs["supplier_pk"], tenant=self.request.user.tenant
        )
        return context

    def form_valid(self, form):
        """Set supplier and uploaded_by before saving."""
        supplier = get_object_or_404(
            Supplier, pk=self.kwargs["supplier_pk"], tenant=self.request.user.tenant
        )
        form.instance.supplier = supplier
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, f"Document '{form.instance.title}' uploaded successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to supplier detail page."""
        return reverse("procurement:supplier_detail", kwargs={"pk": self.kwargs["supplier_pk"]})


@login_required
@tenant_required
@require_http_methods(["POST"])
def update_supplier_rating(request, pk):
    """AJAX view to update supplier rating."""
    supplier = get_object_or_404(Supplier, pk=pk, tenant=request.user.tenant)

    try:
        rating = int(request.POST.get("rating", 0))
        if 0 <= rating <= 5:
            supplier.rating = rating
            supplier.save(update_fields=["rating"])
            return JsonResponse(
                {"success": True, "message": f"Rating updated to {rating} stars", "rating": rating}
            )
        else:
            return JsonResponse({"success": False, "message": "Rating must be between 0 and 5"})
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid rating value"})


@login_required
@tenant_required
def supplier_communications(request, pk):
    """View all communications for a supplier."""
    supplier = get_object_or_404(Supplier, pk=pk, tenant=request.user.tenant)

    communications = supplier.communications.select_related("created_by").prefetch_related(
        "internal_participants"
    )

    # Filter by type
    comm_type = request.GET.get("type")
    if comm_type:
        communications = communications.filter(communication_type=comm_type)

    # Filter by follow-up status
    followup_filter = request.GET.get("followup")
    if followup_filter == "pending":
        communications = communications.filter(requires_followup=True, is_completed=False)
    elif followup_filter == "completed":
        communications = communications.filter(is_completed=True)

    # Pagination
    paginator = Paginator(communications, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "supplier": supplier,
        "communications": page_obj,
        "comm_type": comm_type,
        "followup_filter": followup_filter,
    }

    return render(request, "procurement/supplier_communications.html", context)


@login_required
@tenant_required
def supplier_documents(request, pk):
    """View all documents for a supplier."""
    supplier = get_object_or_404(Supplier, pk=pk, tenant=request.user.tenant)

    documents = supplier.documents.select_related("uploaded_by")

    # Filter by type
    doc_type = request.GET.get("type")
    if doc_type:
        documents = documents.filter(document_type=doc_type)

    # Filter by status
    status_filter = request.GET.get("status")
    if status_filter == "active":
        documents = documents.filter(is_active=True)
    elif status_filter == "expired":
        documents = documents.extra(
            where=["expiry_date IS NOT NULL AND expiry_date < CURRENT_DATE"]
        )
    elif status_filter == "expiring":
        documents = documents.extra(
            where=["expiry_date IS NOT NULL AND expiry_date <= CURRENT_DATE + INTERVAL '30 days'"]
        )

    # Pagination
    paginator = Paginator(documents, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "supplier": supplier,
        "documents": page_obj,
        "doc_type": doc_type,
        "status_filter": status_filter,
    }

    return render(request, "procurement/supplier_documents.html", context)
