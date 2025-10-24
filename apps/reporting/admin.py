"""
Django admin configuration for reporting models.
"""

from django.contrib import admin

from apps.reporting.models import (
    Report,
    ReportCategory,
    ReportExecution,
    ReportParameter,
    ReportSchedule,
)


@admin.register(ReportCategory)
class ReportCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "category_type", "sort_order", "is_active"]
    list_filter = ["category_type", "is_active"]
    search_fields = ["name", "description"]
    ordering = ["sort_order", "name"]


class ReportParameterInline(admin.TabularInline):
    model = ReportParameter
    extra = 0
    fields = ["name", "label", "parameter_type", "is_required", "sort_order"]
    ordering = ["sort_order"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "tenant",
        "category",
        "report_type",
        "status",
        "created_by",
        "run_count",
        "last_run_at",
        "created_at",
    ]
    list_filter = ["report_type", "status", "category", "created_at"]
    search_fields = ["name", "description", "tenant__company_name"]
    readonly_fields = ["id", "run_count", "last_run_at", "created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "tenant",
                    "name",
                    "description",
                    "category",
                    "report_type",
                    "status",
                )
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "query_config",
                    "parameters",
                    "default_parameters",
                    "layout_config",
                    "output_formats",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Access Control", {"fields": ("created_by", "is_public", "allowed_roles")}),
        (
            "Statistics",
            {
                "fields": ("run_count", "last_run_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [ReportParameterInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("tenant", "category", "created_by")


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "report",
        "frequency",
        "status",
        "next_run_at",
        "run_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["frequency", "status", "created_at"]
    search_fields = ["name", "description", "report__name"]
    readonly_fields = ["id", "run_count", "last_run_at", "next_run_at", "created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "report", "name", "description")}),
        (
            "Scheduling",
            {"fields": ("frequency", "cron_expression", "start_date", "end_date", "status")},
        ),
        ("Report Configuration", {"fields": ("parameters", "output_format")}),
        ("Email Delivery", {"fields": ("email_recipients", "email_subject", "email_body")}),
        (
            "Statistics",
            {
                "fields": (
                    "run_count",
                    "last_run_at",
                    "next_run_at",
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("report", "created_by")


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = [
        "report",
        "status",
        "trigger_type",
        "executed_by",
        "row_count",
        "duration_display",
        "started_at",
        "email_sent",
    ]
    list_filter = ["status", "trigger_type", "output_format", "started_at", "email_sent"]
    search_fields = ["report__name", "executed_by__username", "error_message"]
    readonly_fields = [
        "id",
        "duration_seconds",
        "result_file_size",
        "celery_task_id",
        "started_at",
        "completed_at",
    ]

    fieldsets = (
        (
            "Execution Details",
            {
                "fields": (
                    "id",
                    "report",
                    "schedule",
                    "trigger_type",
                    "parameters",
                    "output_format",
                    "executed_by",
                )
            },
        ),
        (
            "Status & Timing",
            {
                "fields": (
                    "status",
                    "started_at",
                    "completed_at",
                    "duration_seconds",
                    "celery_task_id",
                )
            },
        ),
        (
            "Results",
            {"fields": ("result_file_path", "result_file_size", "row_count", "error_message")},
        ),
        ("Email Delivery", {"fields": ("email_sent", "email_recipients")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("report", "schedule", "executed_by")

    def duration_display(self, obj):
        """Display execution duration in human-readable format."""
        return obj.duration_display

    duration_display.short_description = "Duration"

    def has_add_permission(self, request):
        """Disable adding executions through admin."""
        return False


@admin.register(ReportParameter)
class ReportParameterAdmin(admin.ModelAdmin):
    list_display = [
        "report",
        "name",
        "label",
        "parameter_type",
        "is_required",
        "sort_order",
        "group_name",
    ]
    list_filter = ["parameter_type", "is_required"]
    search_fields = ["name", "label", "report__name"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("report", "name", "label", "parameter_type", "description")},
        ),
        ("Validation", {"fields": ("is_required", "default_value", "validation_rules")}),
        (
            "Options",
            {"fields": ("options",), "description": "For SELECT and MULTISELECT parameters"},
        ),
        ("UI Configuration", {"fields": ("sort_order", "group_name", "help_text")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("report")


# Custom admin actions
@admin.action(description="Mark selected schedules as active")
def make_schedules_active(modeladmin, request, queryset):
    queryset.update(status="ACTIVE")


@admin.action(description="Mark selected schedules as paused")
def make_schedules_paused(modeladmin, request, queryset):
    queryset.update(status="PAUSED")


# Add actions to ReportScheduleAdmin
ReportScheduleAdmin.actions = [make_schedules_active, make_schedules_paused]
