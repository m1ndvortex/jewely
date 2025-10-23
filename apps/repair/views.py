"""
Views for repair order management.

This module contains views for creating, updating, and tracking repair orders,
including photo uploads, status updates, and work order generation.
"""

from datetime import date
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.decorators import tenant_required
from apps.core.mixins import TenantRequiredMixin

from .forms import (
    CustomOrderForm,
    RepairOrderForm,
    RepairOrderPhotoForm,
    RepairOrderStatusForm,
    WorkOrderForm,
)
from .models import CustomOrder, RepairOrder


class RepairOrderListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """
    List view for repair orders with filtering and search.

    Displays repair orders for the current tenant with pagination,
    filtering by status, and search functionality.
    """

    model = RepairOrder
    template_name = "repair/repair_order_list.html"
    context_object_name = "repair_orders"
    paginate_by = 20

    def get_queryset(self):
        """Filter repair orders by tenant and apply search/filters."""
        queryset = (
            RepairOrder.objects.filter(tenant=self.request.user.tenant)
            .select_related("customer", "assigned_to")
            .prefetch_related("photos")
        )

        # Apply status filter
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Apply priority filter
        priority = self.request.GET.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        # Apply search
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(order_number__icontains=search)
                | models.Q(customer__first_name__icontains=search)
                | models.Q(customer__last_name__icontains=search)
                | models.Q(item_description__icontains=search)
            )

        # Apply assigned to filter
        assigned_to = self.request.GET.get("assigned_to")
        if assigned_to:
            if assigned_to == "unassigned":
                queryset = queryset.filter(assigned_to__isnull=True)
            else:
                queryset = queryset.filter(assigned_to_id=assigned_to)

        # Apply overdue filter
        overdue = self.request.GET.get("overdue")
        if overdue == "true":
            queryset = queryset.filter(
                estimated_completion__lt=date.today(),
                status__in=["received", "in_progress", "quality_check"],
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)

        # Add filter options
        context["status_choices"] = RepairOrder.STATUS_CHOICES
        context["priority_choices"] = RepairOrder.PRIORITY_CHOICES

        # Add staff members for assignment filter
        from django.contrib.auth import get_user_model

        User = get_user_model()
        context["staff_members"] = User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"],
        )

        # Add current filter values
        context["current_status"] = self.request.GET.get("status", "")
        context["current_priority"] = self.request.GET.get("priority", "")
        context["current_search"] = self.request.GET.get("search", "")
        context["current_assigned_to"] = self.request.GET.get("assigned_to", "")
        context["current_overdue"] = self.request.GET.get("overdue", "")

        return context


class RepairOrderDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """
    Detail view for repair orders.

    Shows complete repair order information including photos,
    status history, and action buttons.
    """

    model = RepairOrder
    template_name = "repair/repair_order_detail.html"
    context_object_name = "repair_order"

    def get_queryset(self):
        """Filter by tenant."""
        return (
            RepairOrder.objects.filter(tenant=self.request.user.tenant)
            .select_related("customer", "assigned_to", "created_by")
            .prefetch_related("photos")
        )

    def get_context_data(self, **kwargs):
        """Add forms and additional context."""
        context = super().get_context_data(**kwargs)

        # Add photo upload form
        context["photo_form"] = RepairOrderPhotoForm()

        # Add status update form
        context["status_form"] = RepairOrderStatusForm(
            instance=self.object, tenant=self.request.user.tenant
        )

        # Add available transitions
        context["available_transitions"] = self._get_available_transitions()

        return context

    def _get_available_transitions(self):
        """Get available FSM transitions for current status."""
        repair_order = self.object
        transitions = []

        if repair_order.can_start_work():
            transitions.append(("start_work", "Start Work"))

        if repair_order.status == "in_progress":
            transitions.append(("submit_for_quality_check", "Submit for Quality Check"))

        if repair_order.status == "quality_check":
            transitions.append(("complete_work", "Mark as Completed"))
            transitions.append(("return_to_work", "Return to Work"))

        if repair_order.can_complete():
            transitions.append(("complete_work", "Mark as Completed"))

        if repair_order.can_deliver():
            transitions.append(("deliver_to_customer", "Mark as Delivered"))

        if repair_order.status in ["received", "in_progress"]:
            transitions.append(("cancel_order", "Cancel Order"))

        return transitions


class RepairOrderCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """
    Create view for new repair orders.

    Handles repair order creation with automatic order number generation.
    """

    model = RepairOrder
    form_class = RepairOrderForm
    template_name = "repair/repair_order_form.html"

    def get_form_kwargs(self):
        """Pass tenant to form."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def form_valid(self, form):
        """Set tenant, created_by, and generate order number."""
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user

        # Generate unique order number
        form.instance.order_number = self._generate_order_number()

        messages.success(
            self.request, f"Repair order {form.instance.order_number} created successfully."
        )
        return super().form_valid(form)

    def _generate_order_number(self):
        """Generate unique repair order number."""
        today = timezone.now().date()
        prefix = f"REP-{today.strftime('%Y%m%d')}"

        # Find the next sequential number for today
        existing_orders = RepairOrder.objects.filter(
            tenant=self.request.user.tenant, order_number__startswith=prefix
        ).count()

        return f"{prefix}-{existing_orders + 1:04d}"

    def get_success_url(self):
        """Redirect to repair order detail."""
        return reverse("repair:repair_detail", kwargs={"pk": self.object.pk})


class RepairOrderUpdateView(LoginRequiredMixin, TenantRequiredMixin, UpdateView):
    """
    Update view for repair orders.

    Allows editing of repair order details.
    """

    model = RepairOrder
    form_class = RepairOrderForm
    template_name = "repair/repair_order_form.html"

    def get_queryset(self):
        """Filter by tenant."""
        return RepairOrder.objects.filter(tenant=self.request.user.tenant)

    def get_form_kwargs(self):
        """Pass tenant to form."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def form_valid(self, form):
        """Show success message."""
        messages.success(
            self.request, f"Repair order {form.instance.order_number} updated successfully."
        )
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to repair order detail."""
        return reverse("repair:repair_detail", kwargs={"pk": self.object.pk})


@login_required
@tenant_required
@require_http_methods(["POST"])
def upload_photo(request, pk):
    """
    AJAX view for uploading photos to repair orders.

    Handles photo upload with validation and returns JSON response.
    """
    repair_order = get_object_or_404(RepairOrder, pk=pk, tenant=request.user.tenant)

    form = RepairOrderPhotoForm(request.POST, request.FILES)

    if form.is_valid():
        photo = form.save(commit=False)
        photo.repair_order = repair_order
        photo.taken_by = request.user
        photo.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Photo uploaded successfully.",
                "photo_id": photo.id,
                "photo_url": photo.photo.url,
                "photo_type": photo.get_photo_type_display(),
                "description": photo.description,
            }
        )
    else:
        return JsonResponse({"success": False, "errors": form.errors}, status=400)


@login_required
@tenant_required
@require_http_methods(["POST"])
def update_status(request, pk):
    """
    AJAX view for updating repair order status.

    Handles FSM transitions and status updates.
    """
    repair_order = get_object_or_404(RepairOrder, pk=pk, tenant=request.user.tenant)

    action = request.POST.get("action")

    try:
        with transaction.atomic():
            if action == "start_work":
                repair_order.start_work(user=request.user)
            elif action == "submit_for_quality_check":
                repair_order.submit_for_quality_check()
                repair_order.save()
            elif action == "return_to_work":
                repair_order.return_to_work()
                repair_order.save()
            elif action == "complete_work":
                repair_order.complete_work()
            elif action == "deliver_to_customer":
                repair_order.deliver_to_customer()
            elif action == "cancel_order":
                repair_order.cancel_order()
                repair_order.save()
            else:
                return JsonResponse({"success": False, "message": "Invalid action."}, status=400)

            # Send notification to customer
            _send_status_notification(repair_order)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Status updated to {repair_order.get_status_display()}.",
                    "new_status": repair_order.status,
                    "new_status_display": repair_order.get_status_display(),
                }
            )

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)


@login_required
@tenant_required
def generate_work_order(request):
    """
    View for generating work orders for craftsmen.

    Allows selection of repair orders to include in a work order PDF.
    """
    if request.method == "POST":
        form = WorkOrderForm(request.POST, tenant=request.user.tenant)

        if form.is_valid():
            repair_orders = form.cleaned_data["repair_orders"]
            craftsman = form.cleaned_data["craftsman"]
            notes = form.cleaned_data["notes"]

            # Generate PDF work order
            response = _generate_work_order_pdf(repair_orders, craftsman, notes)

            # Update repair orders to assign craftsman
            repair_orders.update(assigned_to=craftsman)

            messages.success(request, f"Work order generated for {craftsman.get_full_name()}.")
            return response
    else:
        form = WorkOrderForm(tenant=request.user.tenant)

    return render(request, "repair/work_order_form.html", {"form": form})


def _send_status_notification(repair_order):
    """
    Send notification to customer about status change.

    Uses the repair services module for notification handling.
    """
    from .services import send_repair_status_notification

    return send_repair_status_notification(repair_order)


def _generate_work_order_pdf(repair_orders, craftsman, notes):
    """
    Generate PDF work order for craftsman.

    Creates a formatted PDF with repair order details and instructions.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = Paragraph(f"Work Order - {craftsman.get_full_name()}", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 12))

    # Date
    date_para = Paragraph(f"Date: {timezone.now().strftime('%B %d, %Y')}", styles["Normal"])
    story.append(date_para)
    story.append(Spacer(1, 12))

    # Notes
    if notes:
        notes_para = Paragraph(f"Instructions: {notes}", styles["Normal"])
        story.append(notes_para)
        story.append(Spacer(1, 12))

    # Repair orders table
    data = [["Order #", "Customer", "Item", "Service", "Due Date", "Priority"]]

    for order in repair_orders:
        data.append(
            [
                order.order_number,
                str(order.customer),
                (
                    order.item_description[:50] + "..."
                    if len(order.item_description) > 50
                    else order.item_description
                ),
                order.get_service_type_display(),
                order.estimated_completion.strftime("%m/%d/%Y"),
                order.get_priority_display(),
            ]
        )

    table = Table(data)
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

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # Create response
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="work_order_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    )

    return response


# Custom Order Views


class CustomOrderListView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """List view for custom orders."""

    model = CustomOrder
    template_name = "repair/custom_order_list.html"
    context_object_name = "custom_orders"
    paginate_by = 20

    def get_queryset(self):
        """Filter custom orders by tenant."""
        return (
            CustomOrder.objects.filter(tenant=self.request.user.tenant)
            .select_related("customer", "designer", "craftsman")
            .order_by("-created_at")
        )


class CustomOrderDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """Detail view for custom orders."""

    model = CustomOrder
    template_name = "repair/custom_order_detail.html"
    context_object_name = "custom_order"

    def get_queryset(self):
        """Filter by tenant."""
        return CustomOrder.objects.filter(tenant=self.request.user.tenant).select_related(
            "customer", "designer", "craftsman", "created_by"
        )


class CustomOrderCreateView(LoginRequiredMixin, TenantRequiredMixin, CreateView):
    """Create view for custom orders."""

    model = CustomOrder
    form_class = CustomOrderForm
    template_name = "repair/custom_order_form.html"

    def get_form_kwargs(self):
        """Pass tenant to form."""
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.request.user.tenant
        return kwargs

    def form_valid(self, form):
        """Set tenant, created_by, and generate order number."""
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user

        # Generate unique order number
        form.instance.order_number = self._generate_order_number()

        messages.success(
            self.request, f"Custom order {form.instance.order_number} created successfully."
        )
        return super().form_valid(form)

    def _generate_order_number(self):
        """Generate unique custom order number."""
        today = timezone.now().date()
        prefix = f"CUSTOM-{today.strftime('%Y%m%d')}"

        # Find the next sequential number for today
        existing_orders = CustomOrder.objects.filter(
            tenant=self.request.user.tenant, order_number__startswith=prefix
        ).count()

        return f"{prefix}-{existing_orders + 1:04d}"

    def get_success_url(self):
        """Redirect to custom order detail."""
        return reverse("repair:custom_detail", kwargs={"pk": self.object.pk})
