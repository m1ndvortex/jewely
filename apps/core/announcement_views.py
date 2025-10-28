"""
Views for announcement and communication management.

Per Requirement 31 - Communication and Announcement System
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
        # Mark as sent
        message.mark_as_sent()

        # TODO: Trigger actual delivery via Celery task
        # This would be implemented in a separate task that:
        # 1. Sends email if email channel selected
        # 2. Sends SMS if SMS channel selected
        # 3. Creates in-app notification if in_app channel selected
        # 4. Creates CommunicationLog entry

        messages.success(
            request,
            f"Direct message to {message.tenant.company_name} has been sent.",
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
