"""
Views for procurement management.

This module contains views for supplier management including CRUD operations,
communication tracking, and document management.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.decorators import tenant_required
from apps.core.mixins import TenantMixin

from .forms import (
    GoodsReceiptForm,
    GoodsReceiptItemFormSet,
    PurchaseOrderApprovalForm,
    PurchaseOrderForm,
    PurchaseOrderItemFormSet,
    PurchaseOrderSendForm,
    SupplierCommunicationForm,
    SupplierDocumentForm,
)
from .models import GoodsReceipt, PurchaseOrder, Supplier, SupplierCommunication, SupplierDocument


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


# Purchase Order Views


@method_decorator([login_required, tenant_required], name="dispatch")
class PurchaseOrderListView(TenantMixin, ListView):
    """List view for purchase orders with search and filtering."""

    model = PurchaseOrder
    template_name = "procurement/purchase_order_list.html"
    context_object_name = "purchase_orders"
    paginate_by = 20

    def get_queryset(self):
        """Filter purchase orders by tenant and search query."""
        queryset = PurchaseOrder.objects.filter(tenant=self.request.user.tenant)

        # Search functionality
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(po_number__icontains=search_query)
                | Q(supplier__name__icontains=search_query)
                | Q(supplier_reference__icontains=search_query)
            )

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by supplier
        supplier_filter = self.request.GET.get("supplier")
        if supplier_filter:
            queryset = queryset.filter(supplier_id=supplier_filter)

        # Filter by priority
        priority_filter = self.request.GET.get("priority")
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)

        return queryset.select_related("supplier", "created_by", "approved_by").order_by(
            "-created_at"
        )

    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["supplier_filter"] = self.request.GET.get("supplier", "")
        context["priority_filter"] = self.request.GET.get("priority", "")

        # Add filter options
        context["suppliers"] = Supplier.objects.filter(
            tenant=self.request.user.tenant, is_active=True
        ).order_by("name")
        context["status_choices"] = PurchaseOrder.STATUS_CHOICES
        context["priority_choices"] = PurchaseOrder.PRIORITY_CHOICES

        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class PurchaseOrderDetailView(TenantMixin, DetailView):
    """Detail view for purchase order."""

    model = PurchaseOrder
    template_name = "procurement/purchase_order_detail.html"
    context_object_name = "purchase_order"

    def get_queryset(self):
        """Filter by tenant."""
        return PurchaseOrder.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        """Add related data to context."""
        context = super().get_context_data(**kwargs)
        purchase_order = self.object

        # Check if user can approve this PO
        context["can_approve"] = purchase_order.can_be_approved_by(self.request.user)
        context["required_role"] = purchase_order.get_required_approver_role()

        # Check if user can send this PO
        context["can_send"] = purchase_order.status == "APPROVED" and self.request.user.role in [
            "TENANT_OWNER",
            "TENANT_MANAGER",
        ]

        # Get goods receipts
        context["goods_receipts"] = purchase_order.goods_receipts.select_related(
            "received_by"
        ).order_by("-received_date")

        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class PurchaseOrderCreateView(TenantMixin, CreateView):
    """Create view for purchase orders."""

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "procurement/purchase_order_form.html"

    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        """Add formset to context."""
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["formset"] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = PurchaseOrderItemFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        """Validate form and formset together."""
        context = self.get_context_data()
        formset = context["formset"]

        with transaction.atomic():
            if form.is_valid() and formset.is_valid():
                # Set tenant and created_by
                form.instance.tenant = self.request.user.tenant
                form.instance.created_by = self.request.user

                # Save the purchase order
                self.object = form.save()

                # Save the formset
                formset.instance = self.object
                formset.save()

                # Calculate totals
                self.object.calculate_totals()

                messages.success(
                    self.request,
                    f"Purchase Order {self.object.po_number} created successfully.",
                )
                return redirect(self.get_success_url())
            else:
                return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to purchase order detail page."""
        return reverse("procurement:purchase_order_detail", kwargs={"pk": self.object.pk})


@method_decorator([login_required, tenant_required], name="dispatch")
class PurchaseOrderUpdateView(TenantMixin, UpdateView):
    """Update view for purchase orders (only draft orders can be edited)."""

    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "procurement/purchase_order_form.html"

    def get_queryset(self):
        """Filter by tenant and only allow editing draft orders."""
        return PurchaseOrder.objects.filter(tenant=self.request.user.tenant, status="DRAFT")

    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        """Add formset to context."""
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["formset"] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = PurchaseOrderItemFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        """Validate form and formset together."""
        context = self.get_context_data()
        formset = context["formset"]

        with transaction.atomic():
            if form.is_valid() and formset.is_valid():
                # Save the purchase order
                self.object = form.save()

                # Save the formset
                formset.instance = self.object
                formset.save()

                # Recalculate totals
                self.object.calculate_totals()

                messages.success(
                    self.request,
                    f"Purchase Order {self.object.po_number} updated successfully.",
                )
                return redirect(self.get_success_url())
            else:
                return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to purchase order detail page."""
        return reverse("procurement:purchase_order_detail", kwargs={"pk": self.object.pk})


@login_required
@tenant_required
def purchase_order_approve(request, pk):
    """Approve a purchase order."""
    purchase_order = get_object_or_404(
        PurchaseOrder, pk=pk, tenant=request.user.tenant, status="DRAFT"
    )

    # Check if user can approve this PO
    if not purchase_order.can_be_approved_by(request.user):
        messages.error(
            request,
            f"You don't have permission to approve this purchase order. "
            f"Required role: {purchase_order.get_required_approver_role()}",
        )
        return redirect("procurement:purchase_order_detail", pk=pk)

    if request.method == "POST":
        form = PurchaseOrderApprovalForm(request.POST, purchase_order=purchase_order)
        if form.is_valid():
            # Approve the purchase order
            purchase_order.approve(request.user)
            purchase_order.save()

            # Log approval notes if provided
            approval_notes = form.cleaned_data.get("approval_notes")
            if approval_notes:
                # You could create an approval log model here
                pass

            messages.success(
                request, f"Purchase Order {purchase_order.po_number} approved successfully."
            )
            return redirect("procurement:purchase_order_detail", pk=pk)
    else:
        form = PurchaseOrderApprovalForm(purchase_order=purchase_order)

    context = {
        "purchase_order": purchase_order,
        "form": form,
    }
    return render(request, "procurement/purchase_order_approve.html", context)


@login_required
@tenant_required
def purchase_order_send(request, pk):
    """Send a purchase order to supplier."""
    purchase_order = get_object_or_404(
        PurchaseOrder, pk=pk, tenant=request.user.tenant, status="APPROVED"
    )

    # Check if user can send this PO
    if request.user.role not in ["TENANT_OWNER", "TENANT_MANAGER"]:
        messages.error(request, "You don't have permission to send purchase orders.")
        return redirect("procurement:purchase_order_detail", pk=pk)

    if request.method == "POST":
        form = PurchaseOrderSendForm(request.POST, purchase_order=purchase_order)
        if form.is_valid():
            send_method = form.cleaned_data["send_method"]

            try:
                if send_method in ["EMAIL", "BOTH"]:
                    # Send email
                    _send_purchase_order_email(request, purchase_order, form.cleaned_data)

                if send_method in ["PRINT", "BOTH"]:
                    # Generate PDF
                    pdf_response = _generate_purchase_order_pdf(purchase_order)
                    if send_method == "PRINT":
                        return pdf_response

                # Mark as sent
                purchase_order.send_to_supplier()
                purchase_order.save()

                messages.success(
                    request,
                    f"Purchase Order {purchase_order.po_number} sent to {purchase_order.supplier.name} successfully.",
                )
                return redirect("procurement:purchase_order_detail", pk=pk)

            except Exception as e:
                messages.error(request, f"Error sending purchase order: {str(e)}")
    else:
        form = PurchaseOrderSendForm(purchase_order=purchase_order)

    context = {
        "purchase_order": purchase_order,
        "form": form,
    }
    return render(request, "procurement/purchase_order_send.html", context)


def _send_purchase_order_email(request, purchase_order, form_data):
    """Send purchase order via email."""
    supplier = purchase_order.supplier

    if not supplier.email:
        raise ValueError("Supplier does not have an email address configured.")

    # Format email content
    subject = form_data["email_subject"].format(
        company_name=purchase_order.tenant.company_name,
        po_number=purchase_order.po_number,
    )

    message = form_data["email_message"].format(
        supplier_name=supplier.name,
        po_number=purchase_order.po_number,
        expected_delivery=purchase_order.expected_delivery or "TBD",
        total_amount=f"${purchase_order.total_amount:,.2f}",
        company_name=purchase_order.tenant.company_name,
    )

    # Generate PDF attachment
    pdf_content = _generate_purchase_order_pdf_content(purchase_order)

    # Send email
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=None,  # Use default from email
        to=[supplier.email],
        cc=[request.user.email] if request.user.email else [],
    )

    email.attach(
        f"PO_{purchase_order.po_number}.pdf",
        pdf_content,
        "application/pdf",
    )

    email.send()


def _generate_purchase_order_pdf(purchase_order):
    """Generate PDF response for purchase order."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="PO_{purchase_order.po_number}.pdf"'

    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = Paragraph(f"Purchase Order #{purchase_order.po_number}", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 0.2 * inch))

    # Company and supplier info
    company_info = f"""
    <b>From:</b><br/>
    {purchase_order.tenant.company_name}<br/>
    <br/>
    <b>To:</b><br/>
    {purchase_order.supplier.name}<br/>
    {purchase_order.supplier.contact_person}<br/>
    {purchase_order.supplier.email}<br/>
    {purchase_order.supplier.phone}<br/>
    """

    info_para = Paragraph(company_info, styles["Normal"])
    story.append(info_para)
    story.append(Spacer(1, 0.2 * inch))

    # Order details
    order_info = f"""
    <b>Order Date:</b> {purchase_order.order_date}<br/>
    <b>Expected Delivery:</b> {purchase_order.expected_delivery or 'TBD'}<br/>
    <b>Priority:</b> {purchase_order.get_priority_display()}<br/>
    """

    order_para = Paragraph(order_info, styles["Normal"])
    story.append(order_para)
    story.append(Spacer(1, 0.2 * inch))

    # Items table
    table_data = [["Item", "SKU", "Quantity", "Unit Price", "Total"]]

    for item in purchase_order.items.all():
        table_data.append(
            [
                item.product_name,
                item.product_sku or "-",
                str(item.quantity),
                f"${item.unit_price:,.2f}",
                f"${item.total_price:,.2f}",
            ]
        )

    # Add totals
    table_data.append(["", "", "", "Subtotal:", f"${purchase_order.subtotal:,.2f}"])
    table_data.append(["", "", "", "Tax:", f"${purchase_order.tax_amount:,.2f}"])
    table_data.append(["", "", "", "Total:", f"${purchase_order.total_amount:,.2f}"])

    table = Table(table_data, colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 14),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    story.append(table)

    # Notes
    if purchase_order.notes:
        story.append(Spacer(1, 0.2 * inch))
        notes_para = Paragraph(f"<b>Notes:</b><br/>{purchase_order.notes}", styles["Normal"])
        story.append(notes_para)

    doc.build(story)
    return response


def _generate_purchase_order_pdf_content(purchase_order):
    """Generate PDF content as bytes for email attachment."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = Paragraph(f"Purchase Order #{purchase_order.po_number}", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 0.2 * inch))

    # Company and supplier info
    company_info = f"""
    <b>From:</b><br/>
    {purchase_order.tenant.company_name}<br/>
    <br/>
    <b>To:</b><br/>
    {purchase_order.supplier.name}<br/>
    {purchase_order.supplier.contact_person}<br/>
    {purchase_order.supplier.email}<br/>
    {purchase_order.supplier.phone}<br/>
    """

    info_para = Paragraph(company_info, styles["Normal"])
    story.append(info_para)
    story.append(Spacer(1, 0.2 * inch))

    # Order details
    order_info = f"""
    <b>Order Date:</b> {purchase_order.order_date}<br/>
    <b>Expected Delivery:</b> {purchase_order.expected_delivery or 'TBD'}<br/>
    <b>Priority:</b> {purchase_order.get_priority_display()}<br/>
    """

    order_para = Paragraph(order_info, styles["Normal"])
    story.append(order_para)
    story.append(Spacer(1, 0.2 * inch))

    # Items table
    table_data = [["Item", "SKU", "Quantity", "Unit Price", "Total"]]

    for item in purchase_order.items.all():
        table_data.append(
            [
                item.product_name,
                item.product_sku or "-",
                str(item.quantity),
                f"${item.unit_price:,.2f}",
                f"${item.total_price:,.2f}",
            ]
        )

    # Add totals
    table_data.append(["", "", "", "Subtotal:", f"${purchase_order.subtotal:,.2f}"])
    table_data.append(["", "", "", "Tax:", f"${purchase_order.tax_amount:,.2f}"])
    table_data.append(["", "", "", "Total:", f"${purchase_order.total_amount:,.2f}"])

    table = Table(table_data, colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 14),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    story.append(table)

    # Notes
    if purchase_order.notes:
        story.append(Spacer(1, 0.2 * inch))
        notes_para = Paragraph(f"<b>Notes:</b><br/>{purchase_order.notes}", styles["Normal"])
        story.append(notes_para)

    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content


# Goods Receipt Views


@method_decorator([login_required, tenant_required], name="dispatch")
class GoodsReceiptListView(TenantMixin, ListView):
    """List view for goods receipts with search and filtering."""

    model = GoodsReceipt
    template_name = "procurement/goods_receipt_list.html"
    context_object_name = "goods_receipts"
    paginate_by = 20

    def get_queryset(self):
        """Filter goods receipts by tenant and search query."""
        queryset = GoodsReceipt.objects.filter(tenant=self.request.user.tenant)

        # Search functionality
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search_query)
                | Q(purchase_order__po_number__icontains=search_query)
                | Q(supplier_invoice_number__icontains=search_query)
                | Q(tracking_number__icontains=search_query)
            )

        # Filter by status
        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by purchase order
        po_filter = self.request.GET.get("purchase_order")
        if po_filter:
            queryset = queryset.filter(purchase_order_id=po_filter)

        # Filter by discrepancy
        discrepancy_filter = self.request.GET.get("discrepancy")
        if discrepancy_filter == "yes":
            queryset = queryset.filter(has_discrepancy=True)
        elif discrepancy_filter == "no":
            queryset = queryset.filter(has_discrepancy=False)

        return queryset.select_related("purchase_order", "received_by").order_by("-received_date")

    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["po_filter"] = self.request.GET.get("purchase_order", "")
        context["discrepancy_filter"] = self.request.GET.get("discrepancy", "")

        # Add filter options
        context["purchase_orders"] = PurchaseOrder.objects.filter(
            tenant=self.request.user.tenant, status__in=["SENT", "PARTIALLY_RECEIVED", "COMPLETED"]
        ).order_by("-order_date")
        context["status_choices"] = GoodsReceipt.STATUS_CHOICES

        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class GoodsReceiptDetailView(TenantMixin, DetailView):
    """Detail view for goods receipt."""

    model = GoodsReceipt
    template_name = "procurement/goods_receipt_detail.html"
    context_object_name = "goods_receipt"

    def get_queryset(self):
        """Filter by tenant."""
        return GoodsReceipt.objects.filter(tenant=self.request.user.tenant)

    def get_context_data(self, **kwargs):
        """Add related data to context."""
        context = super().get_context_data(**kwargs)
        goods_receipt = self.object

        # Check if user can complete this receipt
        context["can_complete"] = goods_receipt.status in [
            "PENDING",
            "IN_PROGRESS",
            "DISCREPANCY",
        ] and self.request.user.role in ["TENANT_OWNER", "TENANT_MANAGER"]

        # Three-way matching status
        context["three_way_match"] = goods_receipt.perform_three_way_matching()

        return context


@method_decorator([login_required, tenant_required], name="dispatch")
class GoodsReceiptCreateView(TenantMixin, CreateView):
    """Create view for goods receipts."""

    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = "procurement/goods_receipt_form.html"

    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def get_context_data(self, **kwargs):
        """Add formset to context."""
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["formset"] = GoodsReceiptItemFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = GoodsReceiptItemFormSet(instance=self.object)

        # Add purchase order for formset initialization
        po_id = self.request.GET.get("purchase_order")
        if po_id:
            try:
                context["purchase_order"] = PurchaseOrder.objects.get(
                    id=po_id, tenant=self.request.user.tenant
                )
            except PurchaseOrder.DoesNotExist:
                pass

        return context

    def form_valid(self, form):
        """Validate form and formset together."""
        context = self.get_context_data()
        formset = context["formset"]

        with transaction.atomic():
            if form.is_valid() and formset.is_valid():
                # Set tenant and received_by
                form.instance.tenant = self.request.user.tenant
                form.instance.received_by = self.request.user

                # Save the goods receipt
                self.object = form.save()

                # Save the formset
                formset.instance = self.object
                formset.save()

                # Update purchase order item quantities
                for receipt_item in self.object.items.all():
                    receipt_item.update_inventory()

                # Check if receipt has discrepancies
                has_discrepancy = any(
                    item.has_discrepancy or item.has_quality_issues
                    for item in self.object.items.all()
                )
                if has_discrepancy:
                    self.object.has_discrepancy = True
                    self.object.status = "DISCREPANCY"
                    self.object.save(update_fields=["has_discrepancy", "status"])

                messages.success(
                    self.request,
                    f"Goods Receipt {self.object.receipt_number} created successfully.",
                )
                return redirect(self.get_success_url())
            else:
                return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to goods receipt detail page."""
        return reverse("procurement:goods_receipt_detail", kwargs={"pk": self.object.pk})


@login_required
@tenant_required
def goods_receipt_complete(request, pk):
    """Complete a goods receipt and update inventory."""
    goods_receipt = get_object_or_404(GoodsReceipt, pk=pk, tenant=request.user.tenant)

    # Check if user can complete this receipt
    if request.user.role not in ["TENANT_OWNER", "TENANT_MANAGER"]:
        messages.error(request, "You don't have permission to complete goods receipts.")
        return redirect("procurement:goods_receipt_detail", pk=pk)

    if goods_receipt.status not in ["PENDING", "IN_PROGRESS", "DISCREPANCY"]:
        messages.error(request, "This goods receipt cannot be completed.")
        return redirect("procurement:goods_receipt_detail", pk=pk)

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Update inventory for all accepted items
                for receipt_item in goods_receipt.items.all():
                    if receipt_item.quantity_accepted > 0:
                        # Update PO item received quantities
                        receipt_item.update_inventory()
                        # Create or update inventory item
                        _create_or_update_inventory_item(receipt_item)

                # Mark receipt as completed
                goods_receipt.mark_completed()

                messages.success(
                    request,
                    f"Goods Receipt {goods_receipt.receipt_number} completed successfully. "
                    f"Inventory has been updated.",
                )
                return redirect("procurement:goods_receipt_detail", pk=pk)

        except Exception as e:
            messages.error(request, f"Error completing goods receipt: {str(e)}")

    context = {
        "goods_receipt": goods_receipt,
        "three_way_match": goods_receipt.perform_three_way_matching(),
    }
    return render(request, "procurement/goods_receipt_complete.html", context)


def _create_or_update_inventory_item(receipt_item):
    """
    Create or update inventory item from goods receipt item.

    This function handles the inventory update logic when goods are received.
    """
    from apps.inventory.models import InventoryItem, ProductCategory

    po_item = receipt_item.purchase_order_item
    purchase_order = receipt_item.goods_receipt.purchase_order

    # Try to find existing inventory item by SKU
    existing_item = None
    if po_item.product_sku:
        try:
            existing_item = InventoryItem.objects.get(
                tenant=purchase_order.tenant, sku=po_item.product_sku
            )
        except InventoryItem.DoesNotExist:
            pass

    if existing_item:
        # Update existing inventory
        existing_item.add_quantity(
            receipt_item.quantity_accepted,
            reason=f"Goods receipt {receipt_item.goods_receipt.receipt_number}",
        )
        receipt_item.inventory_item = existing_item
        receipt_item.save(update_fields=["inventory_item"])
    else:
        # Create new inventory item
        # Get or create a default category
        category, _ = ProductCategory.objects.get_or_create(
            tenant=purchase_order.tenant,
            name="Received Items",
            defaults={"description": "Items received from suppliers"},
        )

        # Create new inventory item
        inventory_item = InventoryItem.objects.create(
            tenant=purchase_order.tenant,
            sku=po_item.product_sku or f"REC-{receipt_item.id}",
            name=po_item.product_name,
            category=category,
            karat=18,  # Default karat - should be configurable
            weight_grams=1.0,  # Default weight - should be from PO item
            cost_price=po_item.unit_price,
            selling_price=po_item.unit_price * 1.2,  # 20% markup default
            quantity=receipt_item.quantity_accepted,
            branch=purchase_order.branch or purchase_order.tenant.branches.first(),
            supplier_name=purchase_order.supplier.name,
            supplier_sku=po_item.product_sku,
            notes=f"Received via GR {receipt_item.goods_receipt.receipt_number}",
        )

        receipt_item.inventory_item = inventory_item
        receipt_item.save(update_fields=["inventory_item"])


@login_required
@tenant_required
def purchase_order_receive(request, pk):
    """Quick receive goods for a purchase order."""
    purchase_order = get_object_or_404(PurchaseOrder, pk=pk, tenant=request.user.tenant)

    # Check if PO can be received
    if purchase_order.status not in ["SENT", "PARTIALLY_RECEIVED"]:
        messages.error(request, "This purchase order cannot be received.")
        return redirect("procurement:purchase_order_detail", pk=pk)

    # Redirect to goods receipt creation with pre-filled PO
    return redirect(
        f"{reverse('procurement:goods_receipt_create')}?purchase_order={purchase_order.id}"
    )
