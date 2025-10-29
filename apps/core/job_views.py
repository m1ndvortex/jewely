"""
Job monitoring views for platform administrators.

This module provides views for:
- Job monitoring dashboard
- Active jobs list
- Pending jobs list
- Completed jobs list
- Failed jobs list
- Job statistics

Per Requirement 33 - Scheduled Job Management
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View

from apps.core.admin_views import PlatformAdminRequiredMixin
from apps.core.job_models import JobExecution, JobStatistics
from apps.core.job_service import JobMonitoringService


class JobMonitoringDashboardView(PlatformAdminRequiredMixin, TemplateView):
    """
    Main job monitoring dashboard.

    Requirement 33.1-33.4: Display active, pending, completed, and failed jobs.
    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    template_name = "jobs/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get job counts
        context["active_count"] = len(JobMonitoringService.get_active_jobs())
        context["pending_count"] = len(JobMonitoringService.get_pending_jobs())
        context["completed_count"] = JobExecution.objects.filter(status="SUCCESS").count()
        context["failed_count"] = JobExecution.objects.filter(status="FAILURE").count()

        # Get queue statistics
        context["queue_stats"] = JobMonitoringService.get_queue_stats()

        # Get recent activity
        context["recent_jobs"] = JobExecution.objects.all()[:10]

        # Get performance summary
        context["performance_summary"] = JobMonitoringService.get_performance_summary()

        # Get slow jobs
        context["slow_jobs"] = JobMonitoringService.get_slow_jobs()[:5]

        # Get resource-intensive jobs
        context["resource_intensive_jobs"] = JobMonitoringService.get_resource_intensive_jobs()[:5]

        return context


class ActiveJobsView(PlatformAdminRequiredMixin, TemplateView):
    """
    Display all currently running Celery tasks.

    Requirement 33.1: Display all currently running Celery tasks.
    """

    template_name = "jobs/active_jobs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_jobs"] = JobMonitoringService.get_active_jobs()
        return context


class PendingJobsView(PlatformAdminRequiredMixin, TemplateView):
    """
    Display pending jobs in queue.

    Requirement 33.2: Display pending jobs in queue with priority and ETA.
    """

    template_name = "jobs/pending_jobs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_jobs"] = JobMonitoringService.get_pending_jobs()
        return context


class CompletedJobsView(PlatformAdminRequiredMixin, ListView):
    """
    Display completed jobs.

    Requirement 33.3: Display completed jobs with execution time and status.
    """

    template_name = "jobs/completed_jobs.html"
    context_object_name = "jobs"
    paginate_by = 50

    def get_queryset(self):
        return JobExecution.objects.filter(status__in=["SUCCESS", "REVOKED"]).order_by(
            "-completed_at"
        )


class FailedJobsView(PlatformAdminRequiredMixin, ListView):
    """
    Display failed jobs.

    Requirement 33.4: Display failed jobs with error details and retry options.
    """

    template_name = "jobs/failed_jobs.html"
    context_object_name = "jobs"
    paginate_by = 50

    def get_queryset(self):
        return JobExecution.objects.filter(status="FAILURE").order_by("-completed_at")


class JobDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Display detailed information about a specific job.

    Requirement 33.4: Display failed jobs with error details.
    """

    model = JobExecution
    template_name = "jobs/job_detail.html"
    context_object_name = "job"
    slug_field = "task_id"
    slug_url_kwarg = "task_id"


class JobStatisticsView(PlatformAdminRequiredMixin, ListView):
    """
    Display job statistics.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    template_name = "jobs/statistics.html"
    context_object_name = "statistics"
    paginate_by = 50

    def get_queryset(self):
        return JobStatistics.objects.all().order_by("-total_executions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add performance summary
        context["performance_summary"] = JobMonitoringService.get_performance_summary()

        # Add slow jobs
        context["slow_jobs"] = JobMonitoringService.get_slow_jobs()[:10]

        # Add resource-intensive jobs
        context["resource_intensive_jobs"] = JobMonitoringService.get_resource_intensive_jobs()[:10]

        return context


class JobRetryView(PlatformAdminRequiredMixin, View):
    """
    Retry a failed job.

    Requirement 33.4: Display failed jobs with retry options.
    """

    def post(self, request, task_id):
        success = JobMonitoringService.retry_job(task_id)

        if success:
            messages.success(request, f"Job {task_id} has been queued for retry.")
        else:
            messages.error(request, f"Failed to retry job {task_id}. Job may not be retryable.")

        return redirect("core:job_detail", task_id=task_id)


class JobCancelView(PlatformAdminRequiredMixin, View):
    """
    Cancel a pending or running job.

    Requirement 33.8: Allow administrators to cancel running or pending jobs.
    """

    def post(self, request, task_id):
        success = JobMonitoringService.cancel_job(task_id)

        if success:
            messages.success(request, f"Job {task_id} has been cancelled.")
        else:
            messages.error(request, f"Failed to cancel job {task_id}.")

        return redirect("core:jobs_dashboard")


class JobsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for job monitoring data.

    Provides real-time job data for HTMX updates.
    """

    def get(self, request):
        job_type = request.GET.get("type", "all")

        data = {
            "timestamp": timezone.now().isoformat(),
        }

        if job_type == "active":
            data["jobs"] = JobMonitoringService.get_active_jobs()
        elif job_type == "pending":
            data["jobs"] = JobMonitoringService.get_pending_jobs()
        elif job_type == "completed":
            jobs = JobMonitoringService.get_completed_jobs(limit=50)
            data["jobs"] = [
                {
                    "task_id": job.task_id,
                    "task_name": job.task_name,
                    "status": job.status,
                    "execution_time": job.execution_time,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                }
                for job in jobs
            ]
        elif job_type == "failed":
            jobs = JobMonitoringService.get_failed_jobs(limit=50)
            data["jobs"] = [
                {
                    "task_id": job.task_id,
                    "task_name": job.task_name,
                    "status": job.status,
                    "error": job.error,
                    "can_retry": job.can_retry,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                }
                for job in jobs
            ]
        else:
            # Return summary
            data["active_count"] = len(JobMonitoringService.get_active_jobs())
            data["pending_count"] = len(JobMonitoringService.get_pending_jobs())
            data["completed_count"] = JobExecution.objects.filter(status="SUCCESS").count()
            data["failed_count"] = JobExecution.objects.filter(status="FAILURE").count()
            data["queue_stats"] = JobMonitoringService.get_queue_stats()

        return JsonResponse(data)


class QueueStatsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for queue statistics.

    Requirement 33.2: Display pending jobs in queue with priority.
    """

    def get(self, request):
        queue_stats = JobMonitoringService.get_queue_stats()

        return JsonResponse(
            {
                "queues": queue_stats,
                "timestamp": timezone.now().isoformat(),
            }
        )


class ManualJobTriggerView(PlatformAdminRequiredMixin, TemplateView):
    """
    View for manually triggering jobs.

    Requirement 33.5: Allow administrators to manually trigger scheduled jobs.
    """

    template_name = "jobs/manual_trigger.html"

    def get_context_data(self, **kwargs):
        from apps.core.job_forms import ManualJobTriggerForm

        context = super().get_context_data(**kwargs)
        context["form"] = ManualJobTriggerForm()
        return context

    def post(self, request):
        from apps.core.job_forms import ManualJobTriggerForm
        from apps.core.job_service import JobManagementService

        form = ManualJobTriggerForm(request.POST)

        if form.is_valid():
            task_id = JobManagementService.trigger_job(
                task_name=form.cleaned_data["task_name"],
                args=form.cleaned_data["args"],
                kwargs=form.cleaned_data["kwargs"],
                queue=form.cleaned_data["queue"],
                priority=form.cleaned_data["priority"],
                countdown=form.cleaned_data.get("countdown"),
            )

            if task_id:
                messages.success(
                    request,
                    f"Job triggered successfully. Task ID: {task_id}",  # noqa: F541
                )
                return redirect("core:jobs:detail", task_id=task_id)
            else:
                messages.error(request, "Failed to trigger job.")

        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class JobScheduleListView(PlatformAdminRequiredMixin, ListView):
    """
    View for listing job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    template_name = "jobs/schedule_list.html"
    context_object_name = "schedules"
    paginate_by = 50

    def get_queryset(self):
        from apps.core.job_models import JobSchedule

        return JobSchedule.objects.all().order_by("-enabled", "name")


class JobScheduleCreateView(PlatformAdminRequiredMixin, TemplateView):
    """
    View for creating job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    template_name = "jobs/schedule_form.html"

    def get_context_data(self, **kwargs):
        from apps.core.job_forms import JobScheduleForm

        context = super().get_context_data(**kwargs)
        context["form"] = JobScheduleForm()
        context["action"] = "Create"
        return context

    def post(self, request):
        from apps.core.job_forms import JobScheduleForm
        from apps.core.job_service import JobManagementService

        form = JobScheduleForm(request.POST)

        if form.is_valid():
            schedule = JobManagementService.create_schedule(
                name=f"{form.cleaned_data['task_name']}_schedule_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
                task_name=form.cleaned_data["task_name"],
                schedule_type=form.cleaned_data["schedule_type"],
                cron_expression=form.cleaned_data.get("cron_expression"),
                interval_value=form.cleaned_data.get("interval_value"),
                interval_unit=form.cleaned_data.get("interval_unit"),
                args=form.cleaned_data["args"],
                kwargs=form.cleaned_data["kwargs"],
                queue=form.cleaned_data["queue"],
                priority=form.cleaned_data["priority"],
                enabled=form.cleaned_data["enabled"],
                created_by=request.user,
            )

            if schedule:
                messages.success(request, f"Schedule '{schedule.name}' created successfully.")
                return redirect("core:jobs:schedules")
            else:
                messages.error(request, "Failed to create schedule.")

        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class JobScheduleUpdateView(PlatformAdminRequiredMixin, TemplateView):
    """
    View for updating job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    template_name = "jobs/schedule_form.html"

    def get_context_data(self, **kwargs):
        from apps.core.job_forms import JobScheduleForm
        from apps.core.job_models import JobSchedule

        context = super().get_context_data(**kwargs)
        schedule = JobSchedule.objects.get(pk=kwargs["pk"])

        initial_data = {
            "task_name": schedule.task_name,
            "schedule_type": schedule.schedule_type,
            "cron_expression": schedule.cron_expression,
            "interval_value": schedule.interval_value,
            "interval_unit": schedule.interval_unit,
            "args": schedule.args,
            "kwargs": schedule.kwargs,
            "queue": schedule.queue,
            "priority": schedule.priority,
            "enabled": schedule.enabled,
        }

        context["form"] = JobScheduleForm(initial=initial_data)
        context["schedule"] = schedule
        context["action"] = "Update"
        return context

    def post(self, request, pk):
        from apps.core.job_forms import JobScheduleForm
        from apps.core.job_models import JobSchedule
        from apps.core.job_service import JobManagementService

        schedule = JobSchedule.objects.get(pk=pk)
        form = JobScheduleForm(request.POST)

        if form.is_valid():
            updated = JobManagementService.update_schedule(
                schedule_id=schedule.id,
                task_name=form.cleaned_data["task_name"],
                schedule_type=form.cleaned_data["schedule_type"],
                cron_expression=form.cleaned_data.get("cron_expression"),
                interval_value=form.cleaned_data.get("interval_value"),
                interval_unit=form.cleaned_data.get("interval_unit"),
                args=form.cleaned_data["args"],
                kwargs=form.cleaned_data["kwargs"],
                queue=form.cleaned_data["queue"],
                priority=form.cleaned_data["priority"],
                enabled=form.cleaned_data["enabled"],
            )

            if updated:
                messages.success(request, f"Schedule '{schedule.name}' updated successfully.")
                return redirect("core:jobs:schedules")
            else:
                messages.error(request, "Failed to update schedule.")

        context = self.get_context_data(pk=pk)
        context["form"] = form
        return self.render_to_response(context)


class JobScheduleDeleteView(PlatformAdminRequiredMixin, View):
    """
    View for deleting job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    def post(self, request, pk):
        from apps.core.job_models import JobSchedule

        try:
            schedule = JobSchedule.objects.get(pk=pk)
            schedule_name = schedule.name
            schedule.delete()
            messages.success(request, f"Schedule '{schedule_name}' deleted successfully.")
        except JobSchedule.DoesNotExist:
            messages.error(request, "Schedule not found.")

        return redirect("core:jobs:schedules")


class JobScheduleToggleView(PlatformAdminRequiredMixin, View):
    """
    View for enabling/disabling job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    def post(self, request, pk):
        from apps.core.job_models import JobSchedule

        try:
            schedule = JobSchedule.objects.get(pk=pk)
            schedule.enabled = not schedule.enabled
            schedule.save()

            status = "enabled" if schedule.enabled else "disabled"
            messages.success(request, f"Schedule '{schedule.name}' {status} successfully.")
        except JobSchedule.DoesNotExist:
            messages.error(request, "Schedule not found.")

        return redirect("core:jobs:schedules")


class JobPriorityUpdateView(PlatformAdminRequiredMixin, View):
    """
    View for updating job priority.

    Requirement 33.7: Allow administrators to set job priorities.
    """

    def post(self, request, task_id):
        from apps.core.job_forms import JobPriorityForm
        from apps.core.job_service import JobManagementService

        form = JobPriorityForm(request.POST)

        if form.is_valid():
            success = JobManagementService.update_job_priority(
                task_id=task_id,
                priority=form.cleaned_data["priority"],
                queue=form.cleaned_data.get("queue"),
            )

            if success:
                messages.success(request, "Job priority updated successfully.")
            else:
                messages.error(request, "Failed to update job priority.")
        else:
            messages.error(request, "Invalid form data.")

        return redirect("core:jobs:detail", task_id=task_id)


class JobPerformanceView(PlatformAdminRequiredMixin, TemplateView):
    """
    View for job performance tracking and analysis.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    template_name = "jobs/performance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get performance summary
        context["performance_summary"] = JobMonitoringService.get_performance_summary()

        # Get slow jobs
        context["slow_jobs"] = JobMonitoringService.get_slow_jobs()

        # Get resource-intensive jobs
        context["resource_intensive_jobs"] = JobMonitoringService.get_resource_intensive_jobs()

        # Get all statistics for detailed analysis
        context["all_statistics"] = JobStatistics.objects.all().order_by("-avg_execution_time")

        return context


class JobPerformanceAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for job performance data.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    def get(self, request):
        performance_summary = JobMonitoringService.get_performance_summary()
        slow_jobs = JobMonitoringService.get_slow_jobs()
        resource_intensive = JobMonitoringService.get_resource_intensive_jobs()

        data = {
            "timestamp": timezone.now().isoformat(),
            "summary": performance_summary,
            "slow_jobs": [
                {
                    "task_name": job.task_name,
                    "avg_execution_time": float(job.avg_execution_time),
                    "total_executions": job.total_executions,
                    "success_rate": float(job.success_rate),
                }
                for job in slow_jobs[:10]
            ],
            "resource_intensive_jobs": [
                {
                    "task_name": job.task_name,
                    "avg_cpu_percent": float(job.avg_cpu_percent) if job.avg_cpu_percent else None,
                    "avg_memory_mb": float(job.avg_memory_mb) if job.avg_memory_mb else None,
                    "peak_cpu_percent": (
                        float(job.peak_cpu_percent) if job.peak_cpu_percent else None
                    ),
                    "peak_memory_mb": float(job.peak_memory_mb) if job.peak_memory_mb else None,
                }
                for job in resource_intensive[:10]
            ],
        }

        return JsonResponse(data)
