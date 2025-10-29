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
    # Performance tracking
    path("performance/", job_views.JobPerformanceView.as_view(), name="performance"),
    # Manual trigger
    path("trigger/", job_views.ManualJobTriggerView.as_view(), name="trigger"),
    # Schedules
    path("schedules/", job_views.JobScheduleListView.as_view(), name="schedules"),
    path("schedules/create/", job_views.JobScheduleCreateView.as_view(), name="schedule_create"),
    path(
        "schedules/<int:pk>/update/",
        job_views.JobScheduleUpdateView.as_view(),
        name="schedule_update",
    ),
    path(
        "schedules/<int:pk>/delete/",
        job_views.JobScheduleDeleteView.as_view(),
        name="schedule_delete",
    ),
    path(
        "schedules/<int:pk>/toggle/",
        job_views.JobScheduleToggleView.as_view(),
        name="schedule_toggle",
    ),
    # API endpoints
    path("api/jobs/", job_views.JobsAPIView.as_view(), name="api_jobs"),
    path("api/queues/", job_views.QueueStatsAPIView.as_view(), name="api_queues"),
    path("api/performance/", job_views.JobPerformanceAPIView.as_view(), name="api_performance"),
    # Job detail (must come after specific paths)
    path("<str:task_id>/", job_views.JobDetailView.as_view(), name="detail"),
    # Job actions
    path("<str:task_id>/retry/", job_views.JobRetryView.as_view(), name="retry"),
    path("<str:task_id>/cancel/", job_views.JobCancelView.as_view(), name="cancel"),
    path(
        "<str:task_id>/priority/",
        job_views.JobPriorityUpdateView.as_view(),
        name="update_priority",
    ),
]
