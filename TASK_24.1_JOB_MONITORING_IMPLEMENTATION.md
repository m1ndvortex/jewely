# Task 24.1: Job Monitoring Interface Implementation

## Overview

Implemented a comprehensive job monitoring interface for Celery background tasks, fulfilling Requirement 33 - Scheduled Job Management.

## Implementation Summary

### 1. Models (`apps/core/job_models.py`)

Created two main models:

#### JobExecution Model
- Tracks individual job executions with complete lifecycle information
- Fields: task_id, task_name, status, args, kwargs, timing info, queue, priority, error details, retry tracking
- Properties: `duration_seconds`, `is_running`, `is_failed`, `can_retry`, `eta_display`
- Supports all job statuses: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED

#### JobStatistics Model
- Aggregates statistics for each job type
- Tracks: total/successful/failed executions, avg/min/max execution times, resource usage
- Properties: `success_rate`, `failure_rate`, `is_slow` (>60s average)

### 2. Service Layer (`apps/core/job_service.py`)

Implemented `JobMonitoringService` with methods:

- **`get_active_jobs()`**: Fetches currently running Celery tasks using Celery Inspect API
- **`get_pending_jobs()`**: Retrieves jobs in queue with priority and ETA information
- **`get_completed_jobs(limit)`**: Returns recently completed jobs from database
- **`get_failed_jobs(limit)`**: Returns failed jobs with error details
- **`get_job_by_id(task_id)`**: Retrieves detailed job information
- **`retry_job(task_id)`**: Retries a failed job if eligible
- **`cancel_job(task_id)`**: Cancels a pending or running job
- **`get_job_statistics()`**: Returns statistics for all job types
- **`update_job_statistics(task_name)`**: Updates aggregated statistics
- **`cleanup_old_executions(days)`**: Removes old execution records
- **`get_queue_stats()`**: Returns statistics per queue

### 3. Views (`apps/core/job_views.py`)

Implemented comprehensive views:

#### Dashboard Views
- **JobMonitoringDashboardView**: Main dashboard with job counts, queue stats, recent activity, slow jobs
- **ActiveJobsView**: Display all currently running tasks (Requirement 33.1)
- **PendingJobsView**: Show pending jobs with priority and ETA (Requirement 33.2)
- **CompletedJobsView**: List completed jobs with execution time (Requirement 33.3)
- **FailedJobsView**: Show failed jobs with error details and retry options (Requirement 33.4)

#### Detail and Action Views
- **JobDetailView**: Detailed information about a specific job
- **JobStatisticsView**: Performance metrics for all job types (Requirement 33.9)
- **JobRetryView**: Retry a failed job
- **JobCancelView**: Cancel a pending or running job

#### API Views
- **JobsAPIView**: JSON endpoint for real-time job data
- **QueueStatsAPIView**: JSON endpoint for queue statistics

### 4. URL Configuration (`apps/core/job_urls.py`)

Created URL patterns for all views:
- `/platform/jobs/` - Dashboard
- `/platform/jobs/active/` - Active jobs
- `/platform/jobs/pending/` - Pending jobs
- `/platform/jobs/completed/` - Completed jobs
- `/platform/jobs/failed/` - Failed jobs
- `/platform/jobs/<task_id>/` - Job detail
- `/platform/jobs/<task_id>/retry/` - Retry job
- `/platform/jobs/<task_id>/cancel/` - Cancel job
- `/platform/jobs/stats/` - Statistics
- `/platform/jobs/api/jobs/` - Jobs API
- `/platform/jobs/api/queues/` - Queue stats API

### 5. Templates

Created responsive, dark-mode compatible templates:

- **dashboard.html**: Main dashboard with cards, queue stats, recent activity, slow jobs
- **active_jobs.html**: Table of running tasks with cancel action
- **pending_jobs.html**: Table of queued jobs with priority badges and ETA
- **completed_jobs.html**: Paginated list of successful jobs with execution times
- **failed_jobs.html**: Paginated list of failed jobs with error messages and retry buttons
- **job_detail.html**: Comprehensive job details including args, result, error, traceback
- **statistics.html**: Performance metrics table with success rates and timing stats

### 6. Tests (`apps/core/test_job_monitoring.py`)

Comprehensive test coverage:

- **JobExecutionModelTest**: Tests for job execution model properties and methods
- **JobStatisticsModelTest**: Tests for statistics calculations and slow job detection
- **JobMonitoringServiceTest**: Tests for all service methods with mocked Celery
- **JobMonitoringViewsTest**: Tests for view accessibility and content

## Requirements Fulfilled

✅ **Requirement 33.1**: Display all currently running Celery tasks
- Implemented `get_active_jobs()` using Celery Inspect API
- Created ActiveJobsView with real-time task information

✅ **Requirement 33.2**: Display pending jobs in queue with priority and ETA
- Implemented `get_pending_jobs()` with priority sorting
- Created PendingJobsView with priority badges and ETA display

✅ **Requirement 33.3**: Display completed jobs with execution time and status
- Implemented `get_completed_jobs()` from database
- Created CompletedJobsView with execution time display

✅ **Requirement 33.4**: Display failed jobs with error details and retry options
- Implemented `get_failed_jobs()` with error information
- Created FailedJobsView with error messages and retry functionality
- Implemented retry logic with eligibility checking

✅ **Requirement 33.9**: Track execution times and identify slow jobs
- Implemented JobStatistics model with timing metrics
- Created statistics view highlighting slow jobs (>60s average)

## Key Features

1. **Real-time Monitoring**: Dashboard auto-refreshes every 30 seconds
2. **Priority Visualization**: Color-coded priority badges (red=high, yellow=medium, gray=low)
3. **Status Indicators**: Color-coded status badges for quick identification
4. **Error Details**: Full error messages and tracebacks for failed jobs
5. **Retry Management**: Automatic retry eligibility checking with max retry limits
6. **Job Cancellation**: Ability to cancel running or pending jobs
7. **Queue Statistics**: Per-queue breakdown of active/pending/scheduled jobs
8. **Performance Metrics**: Success rates, execution times, slow job identification
9. **Pagination**: Efficient handling of large job lists
10. **Dark Mode Support**: All templates support light and dark themes

## Integration Points

- **Celery Integration**: Uses Celery Inspect API for real-time job information
- **Database Tracking**: Stores job execution history for analysis
- **Admin Panel**: Integrated into platform admin panel with proper permissions
- **URL Routing**: Added to core URLs under `/platform/jobs/`

## Database Schema

### job_executions Table
- Primary key: id (auto-increment)
- Unique: task_id
- Indexes: task_id, task_name, status, queue, queued_at
- Composite indexes for efficient filtering

### job_statistics Table
- Primary key: id (auto-increment)
- Unique: task_name
- Tracks aggregated metrics per job type

## Security

- All views require `PlatformAdminRequiredMixin` for access control
- Only platform administrators can view and manage jobs
- CSRF protection on all POST actions (retry, cancel)
- Confirmation dialogs for destructive actions

## Performance Considerations

- Pagination on all list views (50 items per page)
- Database indexes on frequently queried fields
- Efficient Celery Inspect API usage
- Optional auto-refresh (can be disabled)

## Future Enhancements

Potential improvements for future tasks:
- Real-time updates using WebSockets or Server-Sent Events
- Job scheduling interface (Task 24.2)
- Resource usage tracking (CPU/memory per job)
- Job performance trends and charts
- Email/SMS alerts for job failures
- Bulk job management actions

## Files Created

1. `apps/core/job_models.py` - Data models
2. `apps/core/job_service.py` - Business logic
3. `apps/core/job_views.py` - View controllers
4. `apps/core/job_urls.py` - URL configuration
5. `apps/core/templates/jobs/dashboard.html` - Dashboard template
6. `apps/core/templates/jobs/active_jobs.html` - Active jobs template
7. `apps/core/templates/jobs/pending_jobs.html` - Pending jobs template
8. `apps/core/templates/jobs/completed_jobs.html` - Completed jobs template
9. `apps/core/templates/jobs/failed_jobs.html` - Failed jobs template
10. `apps/core/templates/jobs/job_detail.html` - Job detail template
11. `apps/core/templates/jobs/statistics.html` - Statistics template
12. `apps/core/test_job_monitoring.py` - Test suite

## Files Modified

1. `apps/core/models.py` - Added job models import
2. `apps/core/urls.py` - Added job monitoring URLs

## Testing

Run tests with:
```bash
docker compose exec web pytest apps/core/test_job_monitoring.py -v
```

## Deployment Notes

1. Run migrations to create job monitoring tables:
   ```bash
   docker compose exec web python manage.py migrate
   ```

2. Access the job monitoring dashboard at:
   ```
   http://localhost:8000/platform/jobs/
   ```

3. Ensure Celery workers are running for real-time monitoring

## Conclusion

Task 24.1 has been successfully implemented with comprehensive job monitoring capabilities. The interface provides platform administrators with complete visibility into Celery background tasks, including active, pending, completed, and failed jobs, along with detailed error information and retry options.
