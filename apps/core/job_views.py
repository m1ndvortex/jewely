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

        # Get slow jobs
        context["slow_jobs"] = JobStatistics.objects.filter(avg_execution_time__gt=60.0).order_by(
            "-avg_execution_time"
        )[:5]

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
    """

    template_name = "jobs/statistics.html"
    context_object_name = "statistics"
    paginate_by = 50

    def get_queryset(self):
        return JobStatistics.objects.all().order_by("-total_executions")


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
