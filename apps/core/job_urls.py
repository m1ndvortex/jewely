"""
URL configuration for job monitoring.

Per Requirement 33 - Scheduled Job Management
"""

from django.urls import path

from apps.core import job_views

app_name = "jobs"

urlpatterns = [
    # Dashboard
    path("", job_views.JobMonitoringDashboardView.as_view(), name="dashboard"),
    # Job lists
    path("active/", job_views.ActiveJobsView.as_view(), name="active"),
    path("pending/", job_views.PendingJobsView.as_view(), name="pending"),
    path("completed/", job_views.CompletedJobsView.as_view(), name="completed"),
    path("failed/", job_views.FailedJobsView.as_view(), name="failed"),
    # Statistics (must come before task_id pattern)
    path("statistics/", job_views.JobStatisticsView.as_view(), name="statistics"),
    # API endpoints
    path("api/jobs/", job_views.JobsAPIView.as_view(), name="api_jobs"),
    path("api/queues/", job_views.QueueStatsAPIView.as_view(), name="api_queues"),
    # Job detail (must come after specific paths)
    path("<str:task_id>/", job_views.JobDetailView.as_view(), name="detail"),
    # Job actions
    path("<str:task_id>/retry/", job_views.JobRetryView.as_view(), name="retry"),
    path("<str:task_id>/cancel/", job_views.JobCancelView.as_view(), name="cancel"),
]
