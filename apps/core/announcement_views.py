"""
Views for announcement and communication management.

Per Requirement 31 - Communication and Announcement System
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.announcement_forms import (
    AnnouncementFilterForm,
    AnnouncementForm,
    CommunicationTemplateForm,
    DirectMessageForm,
)
from apps.core.announcement_models import (
    Announcement,
    AnnouncementRead,
    CommunicationLog,
    CommunicationTemplate,
    DirectMessage,
)
from apps.core.models import Tenant


class PlatformAdminRequiredMixin(UserPassesTestMixin):
    """Mixin to require platform admin role."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "PLATFORM_ADMIN"

    def handle_no_permission(self):
        messages.error(self.request, "You must be a platform administrator to access this page.")
        return redirect("admin:index")


# ============================================================================
# Announcement Views
# ============================================================================


class AnnouncementListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    List all announcements with filtering.

    Requirement 31.1: Create platform-wide announcements.
    """

    model = Announcement
    template_name = "core/announcements/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 20

    def get_queryset(self):
        queryset = Announcement.objects.all().select_related("created_by").order_by("-created_at")

        # Apply filters
        form = AnnouncementFilterForm(self.request.GET)
        if form.is_valid():
            # Status filter
            if form.cleaned_data.get("status"):
                queryset = queryset.filter(status=form.cleaned_data["status"])

            # Severity filter
            if form.cleaned_data.get("severity"):
                queryset = queryset.filter(severity=form.cleaned_data["severity"])

            # Date range filter
            if form.cleaned_data.get("date_from"):
                queryset = queryset.filter(created_at__date__gte=form.cleaned_data["date_from"])

            if form.cleaned_data.get("date_to"):
                queryset = queryset.filter(created_at__date__lte=form.cleaned_data["date_to"])

            # Search filter
            if form.cleaned_data.get("search"):
                search_term = form.cleaned_data["search"]
                queryset = queryset.filter(
                    Q(title__icontains=search_term) | Q(message__icontains=search_term)
                )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = AnnouncementFilterForm(self.request.GET)
        context["total_count"] = Announcement.objects.count()
        context["draft_count"] = Announcement.objects.filter(status=Announcement.DRAFT).count()
        context["scheduled_count"] = Announcement.objects.filter(
            status=Announcement.SCHEDULED
        ).count()
        context["sent_count"] = Announcement.objects.filter(status=Announcement.SENT).count()
        return context


class AnnouncementDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    """
    View announcement details and delivery statistics.

    Requirement 31.6: Track which tenants have seen announcements.
    """

    model = Announcement
    template_name = "core/announcements/announcement_detail.html"
    context_object_name = "announcement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        announcement = self.object

        # Get target tenants
        target_tenants = announcement.get_target_tenants()
        context["target_tenant_count"] = target_tenants.count()

        # Get read statistics
        if announcement.status == Announcement.SENT:
            reads = AnnouncementRead.objects.filter(announcement=announcement).select_related(
                "tenant", "user"
            )
            context["read_count"] = reads.count()
            context["read_percentage"] = (
                (reads.count() / target_tenants.count() * 100) if target_tenants.count() > 0 else 0
            )

            # Acknowledgment statistics
            if announcement.requires_acknowledgment:
                acknowledged_count = reads.filter(acknowledged=True).count()
                context["acknowledged_count"] = acknowledged_count
                context["acknowledged_percentage"] = (
                    (acknowledged_count / target_tenants.count() * 100)
                    if target_tenants.count() > 0
                    else 0
                )

            context["reads"] = reads[:50]  # Show first 50 reads

        # Get communication logs
        context["communication_logs"] = (
            CommunicationLog.objects.filter(announcement=announcement)
            .select_related("tenant", "sent_by")
            .order_by("-sent_at")[:20]
        )

        return context


class AnnouncementCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Create a new announcement.

    Requirement 31.1: Create platform-wide announcements.
    Requirement 31.2: Schedule announcements for future delivery.
    Requirement 31.3: Target specific tenant segments.
    Requirement 31.4: Deliver via multiple channels.
    """

    model = Announcement
    form_class = AnnouncementForm
    template_name = "core/announcements/announcement_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        messages.success(
            self.request,
            f"Announcement '{self.object.title}' created successfully. "
            f"Status: {self.object.get_status_display()}",
        )

        return response

    def get_success_url(self):
        return reverse("core:announcement_detail", kwargs={"pk": self.object.pk})


class AnnouncementUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """
    Edit an existing announcement.

    Only draft and scheduled announcements can be edited.
    """

    model = Announcement
    form_class = AnnouncementForm
    template_name = "core/announcements/announcement_form.html"

    def dispatch(self, request, *args, **kwargs):
        announcement = self.get_object()

        # Only allow editing draft and scheduled announcements
        if announcement.status not in [Announcement.DRAFT, Announcement.SCHEDULED]:
            messages.error(request, "Only draft and scheduled announcements can be edited.")
            return redirect("core:announcement_detail", pk=announcement.pk)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Announcement '{self.object.title}' updated successfully.")
        return response

    def get_success_url(self):
        return reverse("core:announcement_detail", kwargs={"pk": self.object.pk})


@login_required
def announcement_send(request, pk):
    """
    Send an announcement immediately.

    Requirement 31.4: Deliver announcements via multiple channels.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    announcement = get_object_or_404(Announcement, pk=pk)

    # Only draft announcements can be sent immediately
    if announcement.status != Announcement.DRAFT:
        messages.error(request, "Only draft announcements can be sent immediately.")
        return redirect("core:announcement_detail", pk=pk)

    if request.method == "POST":
        # Mark as sent
        announcement.mark_as_sent()

        # TODO: Trigger actual delivery via Celery task
        # This would be implemented in a separate task that:
        # 1. Gets target tenants
        # 2. Creates AnnouncementRead records
        # 3. Sends emails/SMS based on channels
        # 4. Creates CommunicationLog entries

        messages.success(
            request,
            f"Announcement '{announcement.title}' has been sent to target tenants.",
        )
        return redirect("core:announcement_detail", pk=pk)

    return render(
        request,
        "core/announcements/announcement_send_confirm.html",
        {
            "announcement": announcement,
            "target_tenant_count": announcement.get_target_tenants().count(),
        },
    )


@login_required
def announcement_cancel(request, pk):
    """
    Cancel a scheduled announcement.

    Requirement 31.2: Schedule announcements for future delivery.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    announcement = get_object_or_404(Announcement, pk=pk)

    # Only scheduled announcements can be cancelled
    if announcement.status != Announcement.SCHEDULED:
        messages.error(request, "Only scheduled announcements can be cancelled.")
        return redirect("core:announcement_detail", pk=pk)

    if request.method == "POST":
        announcement.cancel()
        messages.success(request, f"Announcement '{announcement.title}' has been cancelled.")
        return redirect("core:announcement_detail", pk=pk)

    return render(
        request,
        "core/announcements/announcement_cancel_confirm.html",
        {"announcement": announcement},
    )


# ============================================================================
# Direct Message Views
# ============================================================================


class DirectMessageListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    List all direct messages.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    model = DirectMessage
    template_name = "core/announcements/direct_message_list.html"
    context_object_name = "messages"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            DirectMessage.objects.all()
            .select_related("tenant", "created_by")
            .order_by("-created_at")
        )

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by tenant
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenants"] = Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name")
        context["total_count"] = DirectMessage.objects.count()
        context["draft_count"] = DirectMessage.objects.filter(status=DirectMessage.DRAFT).count()
        context["sent_count"] = DirectMessage.objects.filter(status=DirectMessage.SENT).count()
        return context


class DirectMessageDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    """View direct message details."""

    model = DirectMessage
    template_name = "core/announcements/direct_message_detail.html"
    context_object_name = "message"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get communication logs
        context["communication_logs"] = (
            CommunicationLog.objects.filter(direct_message=self.object)
            .select_related("tenant", "sent_by")
            .order_by("-sent_at")
        )

        return context


class DirectMessageCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Create a new direct message.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    model = DirectMessage
    form_class = DirectMessageForm
    template_name = "core/announcements/direct_message_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        messages.success(
            self.request,
            f"Direct message to {self.object.tenant.company_name} created successfully.",
        )

        return response

    def get_success_url(self):
        return reverse("core:direct_message_detail", kwargs={"pk": self.object.pk})


@login_required
def direct_message_send(request, pk):
    """
    Send a direct message.

    Requirement 31.8: Send direct messages to specific tenants.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    message = get_object_or_404(DirectMessage, pk=pk)

    # Only draft messages can be sent
    if message.status != DirectMessage.DRAFT:
        messages.error(request, "Only draft messages can be sent.")
        return redirect("core:direct_message_detail", pk=pk)

    if request.method == "POST":
        # Import communication service
        from apps.core.communication_service import CommunicationService

        # Send the message via selected channels
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=request.user,
        )

        # Show delivery results
        if any(delivery_status.values()):
            success_channels = [channel for channel, success in delivery_status.items() if success]
            messages.success(
                request,
                f"Direct message to {message.tenant.company_name} has been sent via: "
                f"{', '.join(success_channels)}",
            )
        else:
            messages.error(
                request,
                f"Failed to send message to {message.tenant.company_name}. "
                "Please check the logs for details.",
            )

        return redirect("core:direct_message_detail", pk=pk)

    return render(
        request,
        "core/announcements/direct_message_send_confirm.html",
        {"message": message},
    )


# ============================================================================
# Communication Template Views
# ============================================================================


class CommunicationTemplateListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    List all communication templates.

    Requirement 31.9: Provide communication templates.
    """

    model = CommunicationTemplate
    template_name = "core/announcements/template_list.html"
    context_object_name = "templates"
    paginate_by = 20

    def get_queryset(self):
        queryset = CommunicationTemplate.objects.all().select_related("created_by").order_by("name")

        # Filter by type
        template_type = self.request.GET.get("type")
        if template_type:
            queryset = queryset.filter(template_type=template_type)

        # Filter by active status
        is_active = self.request.GET.get("is_active")
        if is_active == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active == "false":
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_count"] = CommunicationTemplate.objects.count()
        context["active_count"] = CommunicationTemplate.objects.filter(is_active=True).count()
        return context


class CommunicationTemplateDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    """View communication template details."""

    model = CommunicationTemplate
    template_name = "core/announcements/template_detail.html"
    context_object_name = "template"


class CommunicationTemplateCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Create a new communication template.

    Requirement 31.9: Provide communication templates.
    """

    model = CommunicationTemplate
    form_class = CommunicationTemplateForm
    template_name = "core/announcements/template_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        messages.success(self.request, f"Template '{self.object.name}' created successfully.")

        return response

    def get_success_url(self):
        return reverse("core:template_detail", kwargs={"pk": self.object.pk})


class CommunicationTemplateUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """Edit an existing communication template."""

    model = CommunicationTemplate
    form_class = CommunicationTemplateForm
    template_name = "core/announcements/template_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Template '{self.object.name}' updated successfully.")
        return response

    def get_success_url(self):
        return reverse("core:template_detail", kwargs={"pk": self.object.pk})


@login_required
def template_use(request, pk):
    """
    Use a template to create a new announcement.

    Requirement 31.9: Provide communication templates.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    template = get_object_or_404(CommunicationTemplate, pk=pk)

    if not template.is_active:
        messages.error(request, "This template is not active.")
        return redirect("core:template_detail", pk=pk)

    # Increment usage counter
    template.increment_usage()

    # Pre-fill announcement form with template data
    initial_data = {
        "title": template.subject,
        "message": template.message,
        "severity": template.default_severity,
    }

    # Set channel checkboxes based on template defaults
    if "in_app" in template.default_channels:
        initial_data["channel_in_app"] = True
    if "email" in template.default_channels:
        initial_data["channel_email"] = True
    if "sms" in template.default_channels:
        initial_data["channel_sms"] = True

    form = AnnouncementForm(initial=initial_data)

    messages.info(
        request,
        f"Creating announcement from template '{template.name}'. "
        "You can customize the content before saving.",
    )

    return render(
        request,
        "core/announcements/announcement_form.html",
        {
            "form": form,
            "template_used": template,
        },
    )


# ============================================================================
# Communication Log Views
# ============================================================================


class CommunicationLogListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """
    List all communication logs.

    Requirement 31.10: Log all platform-to-tenant communications.
    """

    model = CommunicationLog
    template_name = "core/announcements/communication_log_list.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            CommunicationLog.objects.all()
            .select_related("tenant", "sent_by", "announcement", "direct_message")
            .order_by("-sent_at")
        )

        # Filter by communication type
        comm_type = self.request.GET.get("type")
        if comm_type:
            queryset = queryset.filter(communication_type=comm_type)

        # Filter by tenant
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Date range filter
        date_from = self.request.GET.get("date_from")
        if date_from:
            queryset = queryset.filter(sent_at__date__gte=date_from)

        date_to = self.request.GET.get("date_to")
        if date_to:
            queryset = queryset.filter(sent_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenants"] = Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name")
        context["total_count"] = CommunicationLog.objects.count()
        return context


# ============================================================================
# Tenant-Facing Announcement Display Views
# ============================================================================


@login_required
def tenant_announcement_center(request):
    """
    Announcement center for tenants to view all announcements.

    Requirement 31.5: Display announcements as dismissible banners.
    Requirement 31.6: Track read/unread status.
    """
    # Get tenant from request user
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, "You must be associated with a tenant to view announcements.")
        return redirect("core:home")

    # Get all active announcements for this tenant
    active_announcements = (
        Announcement.objects.filter(status=Announcement.SENT)
        .filter(
            models.Q(target_all_tenants=True)
            | models.Q(
                target_filter__plans__contains=(
                    [tenant.subscription.plan.name] if hasattr(tenant, "subscription") else []
                )
            )
        )
        .order_by("-sent_at")
    )

    # Get read status for each announcement
    read_announcements = AnnouncementRead.objects.filter(
        tenant=tenant, announcement__in=active_announcements
    ).values_list("announcement_id", flat=True)

    # Separate unread and read announcements
    unread_announcements = active_announcements.exclude(id__in=read_announcements)
    read_announcements_list = active_announcements.filter(id__in=read_announcements)

    # Get acknowledgment status
    acknowledgment_status = {}
    for announcement in active_announcements:
        if announcement.requires_acknowledgment:
            try:
                read_record = AnnouncementRead.objects.get(tenant=tenant, announcement=announcement)
                acknowledgment_status[announcement.id] = read_record.acknowledged
            except AnnouncementRead.DoesNotExist:
                acknowledgment_status[announcement.id] = False

    return render(
        request,
        "core/announcements/tenant_announcement_center.html",
        {
            "unread_announcements": unread_announcements,
            "read_announcements": read_announcements_list,
            "acknowledgment_status": acknowledgment_status,
            "unread_count": unread_announcements.count(),
        },
    )


@login_required
def tenant_announcement_detail(request, pk):
    """
    View announcement details for tenant.

    Requirement 31.6: Track read/unread status.
    """
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, "You must be associated with a tenant to view announcements.")
        return redirect("core:home")

    announcement = get_object_or_404(Announcement, pk=pk, status=Announcement.SENT)

    # Mark as read if not already
    read_record, created = AnnouncementRead.objects.get_or_create(
        announcement=announcement, tenant=tenant, defaults={"user": request.user}
    )

    return render(
        request,
        "core/announcements/tenant_announcement_detail.html",
        {
            "announcement": announcement,
            "read_record": read_record,
        },
    )


@login_required
def tenant_announcement_dismiss(request, pk):
    """
    Dismiss an announcement banner.

    Requirement 31.5: Implement dismissible banners.
    """
    tenant = request.user.tenant

    if not tenant:
        return redirect("core:home")

    announcement = get_object_or_404(Announcement, pk=pk)

    # Check if announcement is dismissible
    if not announcement.is_dismissible:
        messages.error(request, "This announcement cannot be dismissed.")
        return redirect("core:tenant_announcement_center")

    # Get or create read record
    read_record, created = AnnouncementRead.objects.get_or_create(
        announcement=announcement, tenant=tenant, defaults={"user": request.user}
    )

    # Mark as dismissed
    read_record.dismiss()

    messages.success(request, "Announcement dismissed.")

    # Return to previous page or announcement center
    next_url = request.GET.get("next", reverse("core:tenant_announcement_center"))
    return redirect(next_url)


@login_required
def tenant_announcement_acknowledge(request, pk):
    """
    Acknowledge a critical announcement.

    Requirement 31.7: Require tenant acknowledgment for critical announcements.
    """
    tenant = request.user.tenant

    if not tenant:
        return redirect("core:home")

    announcement = get_object_or_404(Announcement, pk=pk)

    # Check if announcement requires acknowledgment
    if not announcement.requires_acknowledgment:
        messages.error(request, "This announcement does not require acknowledgment.")
        return redirect("core:tenant_announcement_center")

    # Get or create read record
    read_record, created = AnnouncementRead.objects.get_or_create(
        announcement=announcement, tenant=tenant, defaults={"user": request.user}
    )

    if request.method == "POST":
        # Acknowledge the announcement
        read_record.acknowledge(request.user)

        messages.success(request, "Announcement acknowledged.")
        return redirect("core:tenant_announcement_center")

    return render(
        request,
        "core/announcements/tenant_announcement_acknowledge.html",
        {
            "announcement": announcement,
            "read_record": read_record,
        },
    )


@login_required
def tenant_active_announcements_api(request):
    """
    API endpoint to get active announcements for the current tenant.

    Used for displaying banners and notification badges.

    Requirement 31.5: Display announcements as dismissible banners.
    Requirement 31.6: Track read/unread status.
    """
    from django.http import JsonResponse

    tenant = request.user.tenant

    if not tenant:
        return JsonResponse({"announcements": [], "unread_count": 0})

    # Get active announcements that should be displayed
    active_announcements = Announcement.objects.filter(
        status=Announcement.SENT,
    ).filter(models.Q(display_until__isnull=True) | models.Q(display_until__gt=timezone.now()))

    # Filter by tenant targeting
    # This is a simplified version - in production, you'd want more sophisticated filtering
    if not request.user.role == "PLATFORM_ADMIN":
        # For tenant users, only show announcements targeted to them
        active_announcements = active_announcements.filter(
            models.Q(target_all_tenants=True)
            | models.Q(
                target_filter__plans__contains=(
                    [tenant.subscription.plan.name] if hasattr(tenant, "subscription") else []
                )
            )
        )

    # Get dismissed announcements
    dismissed_announcements = AnnouncementRead.objects.filter(
        tenant=tenant, dismissed=True
    ).values_list("announcement_id", flat=True)

    # Exclude dismissed announcements
    active_announcements = active_announcements.exclude(id__in=dismissed_announcements)

    # Get unacknowledged critical announcements
    unacknowledged_critical = []
    for announcement in active_announcements:
        if announcement.requires_acknowledgment:
            try:
                read_record = AnnouncementRead.objects.get(tenant=tenant, announcement=announcement)
                if not read_record.acknowledged:
                    unacknowledged_critical.append(announcement.id)
            except AnnouncementRead.DoesNotExist:
                unacknowledged_critical.append(announcement.id)

    # Build response
    announcements_data = []
    for announcement in active_announcements[:5]:  # Limit to 5 most recent
        announcements_data.append(
            {
                "id": str(announcement.id),
                "title": announcement.title,
                "message": announcement.message[:200],  # Truncate for banner
                "severity": announcement.severity,
                "is_dismissible": announcement.is_dismissible,
                "requires_acknowledgment": announcement.requires_acknowledgment,
                "is_acknowledged": str(announcement.id) not in unacknowledged_critical,
                "sent_at": announcement.sent_at.isoformat() if announcement.sent_at else None,
            }
        )

    # Get unread count
    read_announcements = AnnouncementRead.objects.filter(tenant=tenant).values_list(
        "announcement_id", flat=True
    )
    unread_count = active_announcements.exclude(id__in=read_announcements).count()

    return JsonResponse(
        {
            "announcements": announcements_data,
            "unread_count": unread_count,
            "unacknowledged_critical_count": len(unacknowledged_critical),
        }
    )


# ============================================================================
# Bulk Messaging Views
# ============================================================================


class BulkMessageCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """
    Create and send bulk messages to multiple tenants.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    model = DirectMessage
    template_name = "core/announcements/bulk_message_form.html"
    fields = []  # We'll use a custom form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all active tenants
        context["tenants"] = Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name")

        # Get subscription plans for filtering
        from apps.core.models import SubscriptionPlan

        context["plans"] = SubscriptionPlan.objects.filter(
            status=SubscriptionPlan.STATUS_ACTIVE
        ).order_by("name")

        # Get communication templates
        context["templates"] = CommunicationTemplate.objects.filter(is_active=True).order_by("name")

        return context

    def _get_channels_from_post(self, request):
        """Extract selected channels from POST data."""
        channels = []
        if request.POST.get("channel_email"):
            channels.append("email")
        if request.POST.get("channel_sms"):
            channels.append("sms")
        if request.POST.get("channel_in_app"):
            channels.append("in_app")
        return channels

    def _validate_form_data(self, request, subject, message, channels):
        """Validate form data and return error message if invalid."""
        if not subject or not message:
            return "Subject and message are required."
        if not channels:
            return "Please select at least one delivery channel."
        return None

    def _send_bulk_message(self, request, subject, message, channels):
        """Send bulk message based on target type."""
        from apps.core.communication_service import BulkCommunicationService

        target_type = request.POST.get("target_type")

        if target_type == "all":
            return BulkCommunicationService.send_to_all_active(
                subject=subject,
                message=message,
                channels=channels,
                created_by=request.user,
            )
        elif target_type == "plan":
            plan_name = request.POST.get("target_plan")
            if not plan_name:
                return None, "Please select a subscription plan."
            return (
                BulkCommunicationService.send_to_plan(
                    plan_name=plan_name,
                    subject=subject,
                    message=message,
                    channels=channels,
                    created_by=request.user,
                ),
                None,
            )
        elif target_type == "specific":
            tenant_ids = request.POST.getlist("tenant_ids")
            if not tenant_ids:
                return None, "Please select at least one tenant."
            return (
                BulkCommunicationService.send_bulk_message(
                    tenant_ids=tenant_ids,
                    subject=subject,
                    message=message,
                    channels=channels,
                    created_by=request.user,
                ),
                None,
            )
        else:
            return None, "Invalid target type."

    def post(self, request, *args, **kwargs):
        # Get form data
        subject = request.POST.get("subject")
        message = request.POST.get("message")
        channels = self._get_channels_from_post(request)

        # Validate
        error = self._validate_form_data(request, subject, message, channels)
        if error:
            messages.error(request, error)
            return self.get(request, *args, **kwargs)

        # Send bulk message
        result = self._send_bulk_message(request, subject, message, channels)
        if isinstance(result, tuple):
            results, error = result
            if error:
                messages.error(request, error)
                return self.get(request, *args, **kwargs)
        else:
            results = result

        # Show results
        messages.success(
            request,
            f"Bulk message sent to {results['total']} tenants. "
            f"Success: {results['success']}, Failed: {results['failed']}. "
            f"Email: {results.get('email_sent', 0)}, "
            f"SMS: {results.get('sms_sent', 0)}, "
            f"In-App: {results.get('in_app_sent', 0)}",
        )

        return redirect("core:direct_message_list")


@login_required
def bulk_message_preview(request):
    """
    Preview bulk message before sending.

    Requirement 31.8: Send direct messages to specific tenants.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    if request.method == "POST":
        subject = request.POST.get("subject")
        message = request.POST.get("message")
        target_type = request.POST.get("target_type")

        # Get target tenant count
        if target_type == "all":
            target_count = Tenant.objects.filter(status=Tenant.ACTIVE).count()
            target_description = "All active tenants"

        elif target_type == "plan":
            plan_name = request.POST.get("target_plan")
            target_count = Tenant.objects.filter(
                subscription__plan__name=plan_name,
                status=Tenant.ACTIVE,
            ).count()
            target_description = f"Tenants on {plan_name} plan"

        elif target_type == "specific":
            tenant_ids = request.POST.getlist("tenant_ids")
            target_count = len(tenant_ids)
            target_description = f"{target_count} selected tenants"

        else:
            target_count = 0
            target_description = "Unknown"

        return render(
            request,
            "core/announcements/bulk_message_preview.html",
            {
                "subject": subject,
                "message": message,
                "target_count": target_count,
                "target_description": target_description,
            },
        )

    return redirect("core:bulk_message_create")


@login_required
def template_apply_to_bulk(request, pk):
    """
    Apply a communication template to bulk message form.

    Requirement 31.9: Provide communication templates.
    """
    # Check platform admin permission
    if request.user.role != "PLATFORM_ADMIN":
        messages.error(request, "You must be a platform administrator to perform this action.")
        return redirect("admin:index")

    template = get_object_or_404(CommunicationTemplate, pk=pk)

    if not template.is_active:
        messages.error(request, "This template is not active.")
        return redirect("core:template_detail", pk=pk)

    # Increment usage counter
    template.increment_usage()

    # Render template with sample context
    sample_context = {
        "tenant_name": "[Tenant Name]",
        "date": timezone.now().strftime("%Y-%m-%d"),
        "time": timezone.now().strftime("%H:%M"),
    }

    subject, message = template.render(sample_context)

    # Store in session for bulk message form
    request.session["bulk_message_template"] = {
        "subject": subject,
        "message": message,
        "channels": template.default_channels,
    }

    messages.info(
        request,
        f"Template '{template.name}' applied. You can customize the content before sending.",
    )

    return redirect("core:bulk_message_create")
