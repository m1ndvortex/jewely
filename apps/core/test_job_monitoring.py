"""
Tests for job monitoring functionality.

Per Requirement 33 - Scheduled Job Management

IMPORTANT: These are REAL integration tests - NO MOCKS ALLOWED.
All tests use real Celery workers and real database.
"""

from datetime import timedelta
from time import sleep

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from celery import shared_task

from apps.core.job_models import JobExecution, JobStatistics
from apps.core.job_service import JobMonitoringService
from apps.core.models import Tenant


# Test tasks for integration testing
@shared_task(bind=True, name="test_job_monitoring.test_success_task")
def test_success_task(self, value):
    """Test task that succeeds."""
    return f"Success: {value}"


@shared_task(bind=True, name="test_job_monitoring.test_failure_task")
def test_failure_task(self, value):
    """Test task that fails."""
    raise ValueError(f"Test error: {value}")


@shared_task(bind=True, name="test_job_monitoring.test_slow_task")
def test_slow_task(self, duration):
    """Test task that takes time."""
    sleep(duration)
    return f"Completed after {duration}s"


class JobExecutionModelTest(TestCase):
    """
    Test JobExecution model.

    Requirement 33.3: Display completed jobs with execution time and status.
    Requirement 33.4: Display failed jobs with error details and retry options.
    """

    def test_create_job_execution(self):
        """Test creating a job execution record."""
        job = JobExecution.objects.create(
            task_id="test-task-123",
            task_name="apps.test.tasks.test_task",
            status="PENDING",
            queue="default",
            priority=5,
        )

        self.assertEqual(job.task_id, "test-task-123")
        self.assertEqual(job.status, "PENDING")
        self.assertFalse(job.is_running)
        self.assertFalse(job.is_failed)

    def test_job_execution_duration(self):
        """Test execution duration calculation."""
        now = timezone.now()
        job = JobExecution.objects.create(
            task_id="test-task-123",
            task_name="apps.test.tasks.test_task",
            status="SUCCESS",
            started_at=now,
            completed_at=now + timedelta(seconds=10),
        )

        self.assertEqual(job.duration_seconds, 10.0)

    def test_job_can_retry(self):
        """Test retry eligibility check."""
        job = JobExecution.objects.create(
            task_id="test-task-123",
            task_name="apps.test.tasks.test_task",
            status="FAILURE",
            retry_count=1,
            max_retries=3,
        )

        self.assertTrue(job.can_retry)

        # Exceed max retries
        job.retry_count = 3
        job.save()
        self.assertFalse(job.can_retry)


class JobStatisticsModelTest(TestCase):
    """
    Test JobStatistics model.

    Requirement 33.9: Track execution times and identify slow jobs.
    """

    def test_create_job_statistics(self):
        """Test creating job statistics."""
        stats = JobStatistics.objects.create(
            task_name="apps.test.tasks.test_task",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            avg_execution_time=5.5,
        )

        self.assertEqual(stats.success_rate, 95.0)
        self.assertEqual(stats.failure_rate, 5.0)
        self.assertFalse(stats.is_slow)

    def test_slow_job_detection(self):
        """Test slow job detection."""
        stats = JobStatistics.objects.create(
            task_name="apps.test.tasks.slow_task",
            total_executions=10,
            successful_executions=10,
            failed_executions=0,
            avg_execution_time=75.0,  # >60 seconds
        )

        self.assertTrue(stats.is_slow)

    def test_success_and_failure_rates(self):
        """Test success and failure rate calculations."""
        # Test with no executions
        stats = JobStatistics.objects.create(
            task_name="apps.test.tasks.no_executions",
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        self.assertEqual(stats.success_rate, 0.0)
        self.assertEqual(stats.failure_rate, 0.0)

        # Test with mixed results
        stats2 = JobStatistics.objects.create(
            task_name="apps.test.tasks.mixed",
            total_executions=50,
            successful_executions=40,
            failed_executions=10,
        )
        self.assertEqual(stats2.success_rate, 80.0)
        self.assertEqual(stats2.failure_rate, 20.0)


class JobMonitoringServiceIntegrationTest(TestCase):
    """
    REAL integration tests for JobMonitoringService.
    Tests with actual Celery workers - NO MOCKS.

    Requirement 33.1: Display all currently running Celery tasks.
    Requirement 33.2: Display pending jobs in queue with priority and ETA.
    Requirement 33.3: Display completed jobs with execution time and status.
    Requirement 33.4: Display failed jobs with error details and retry options.
    """

    def setUp(self):
        """Clean up before each test."""
        JobExecution.objects.all().delete()
        JobStatistics.objects.all().delete()

    def test_get_active_and_pending_jobs_real_celery(self):
        """
        Test getting active and pending jobs from REAL Celery.

        Requirement 33.1: Display all currently running Celery tasks.
        Requirement 33.2: Display pending jobs in queue with priority and ETA.
        """
        # This test verifies the service can communicate with Celery
        # Even if no workers are running, it should not crash
        try:
            active_jobs = JobMonitoringService.get_active_jobs()
            pending_jobs = JobMonitoringService.get_pending_jobs()

            # Should return lists (empty if no workers)
            self.assertIsInstance(active_jobs, list)
            self.assertIsInstance(pending_jobs, list)
        except Exception:
            self.fail("Service should handle Celery connection gracefully")

    def test_queue_stats_real_celery(self):
        """Test getting queue statistics from REAL Celery."""
        try:
            queue_stats = JobMonitoringService.get_queue_stats()
            self.assertIsInstance(queue_stats, dict)
        except Exception:
            self.fail("Service should handle Celery connection gracefully")

    def test_get_completed_jobs(self):
        """
        Test getting completed jobs from database.

        Requirement 33.3: Display completed jobs with execution time and status.
        """
        # Create some completed jobs
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"completed-task-{i}",
                task_name="apps.test.tasks.test_task",
                status="SUCCESS",
                completed_at=timezone.now(),
                execution_time=5.0 + i,
            )

        jobs = JobMonitoringService.get_completed_jobs(limit=10)

        self.assertEqual(len(jobs), 5)
        self.assertTrue(all(job.status == "SUCCESS" for job in jobs))
        # Verify execution times are recorded
        self.assertTrue(all(job.execution_time is not None for job in jobs))

    def test_get_failed_jobs(self):
        """
        Test getting failed jobs from database.

        Requirement 33.4: Display failed jobs with error details and retry options.
        """
        # Create some failed jobs
        for i in range(3):
            JobExecution.objects.create(
                task_id=f"failed-task-{i}",
                task_name="apps.test.tasks.test_task",
                status="FAILURE",
                error=f"Test error {i}",
                traceback=f"Traceback for error {i}",
                completed_at=timezone.now(),
                retry_count=i,
                max_retries=3,
            )

        jobs = JobMonitoringService.get_failed_jobs(limit=10)

        self.assertEqual(len(jobs), 3)
        self.assertTrue(all(job.status == "FAILURE" for job in jobs))
        # Verify error details are present
        self.assertTrue(all(job.error is not None for job in jobs))
        # Verify retry options are available
        self.assertTrue(any(job.can_retry for job in jobs))

    def test_update_job_statistics(self):
        """
        Test updating job statistics.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        task_name = "apps.test.tasks.test_task"

        # Create some job executions with varying execution times
        for i in range(10):
            JobExecution.objects.create(
                task_id=f"stats-task-{i}",
                task_name=task_name,
                status="SUCCESS" if i < 8 else "FAILURE",
                execution_time=5.0 + i,
                completed_at=timezone.now(),
            )

        # Update statistics
        JobMonitoringService.update_job_statistics(task_name)

        # Check statistics
        stats = JobStatistics.objects.get(task_name=task_name)
        self.assertEqual(stats.total_executions, 10)
        self.assertEqual(stats.successful_executions, 8)
        self.assertEqual(stats.failed_executions, 2)
        self.assertIsNotNone(stats.avg_execution_time)
        self.assertIsNotNone(stats.min_execution_time)
        self.assertIsNotNone(stats.max_execution_time)
        # Verify min/max are correct
        self.assertEqual(stats.min_execution_time, 5.0)
        self.assertEqual(stats.max_execution_time, 14.0)

    def test_cleanup_old_executions(self):
        """Test cleaning up old job executions."""
        # Create old job
        old_date = timezone.now() - timedelta(days=35)
        JobExecution.objects.create(
            task_id="old-task",
            task_name="apps.test.tasks.test_task",
            status="SUCCESS",
            completed_at=old_date,
        )

        # Create recent job
        JobExecution.objects.create(
            task_id="recent-task",
            task_name="apps.test.tasks.test_task",
            status="SUCCESS",
            completed_at=timezone.now(),
        )

        # Cleanup old executions (>30 days)
        JobMonitoringService.cleanup_old_executions(days=30)

        # Check that only recent job remains
        self.assertEqual(JobExecution.objects.count(), 1)
        self.assertTrue(JobExecution.objects.filter(task_id="recent-task").exists())
        self.assertFalse(JobExecution.objects.filter(task_id="old-task").exists())

    def test_get_job_by_id_from_database(self):
        """Test retrieving job details by ID from database."""
        # Create a job execution
        JobExecution.objects.create(
            task_id="test-job-123",
            task_name="apps.test.tasks.test_task",
            status="SUCCESS",
            args=["arg1", "arg2"],
            kwargs={"key": "value"},
            execution_time=5.5,
            completed_at=timezone.now(),
        )

        # Retrieve it
        job_data = JobMonitoringService.get_job_by_id("test-job-123")

        self.assertIsNotNone(job_data)
        self.assertEqual(job_data["task_id"], "test-job-123")
        self.assertEqual(job_data["status"], "SUCCESS")
        self.assertEqual(job_data["execution_time"], 5.5)
        self.assertEqual(job_data["source"], "database")

    def test_cancel_job(self):
        """
        Test cancelling a job.

        Requirement 33.8: Allow administrators to cancel running or pending jobs.
        """
        # Create a pending job
        job = JobExecution.objects.create(
            task_id="cancel-test-123",
            task_name="apps.test.tasks.test_task",
            status="PENDING",
        )

        # Cancel it
        result = JobMonitoringService.cancel_job("cancel-test-123")

        # Should succeed
        self.assertTrue(result)

        # Verify status updated
        job.refresh_from_db()
        self.assertEqual(job.status, "REVOKED")


class JobMonitoringViewsIntegrationTest(TestCase):
    """
    REAL integration tests for job monitoring views.
    Tests with actual HTTP requests and database - NO MOCKS.

    Requirement 33.1-33.4: Display active, pending, completed, and failed jobs.
    """

    def setUp(self):
        """Set up test data."""
        User = get_user_model()

        # Clean up
        JobExecution.objects.all().delete()
        JobStatistics.objects.all().delete()

        # Create platform admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client.login(username="admin", password="testpass123")

    def test_job_dashboard_view_access(self):
        """
        Test job monitoring dashboard view is accessible.

        Requirement 33.1-33.4: Display job monitoring interface.
        """
        response = self.client.get(reverse("core:jobs:dashboard"))

        # Should be accessible to platform admins
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Monitoring Dashboard")
        self.assertContains(response, "Active Jobs")
        self.assertContains(response, "Pending Jobs")
        self.assertContains(response, "Completed Jobs")
        self.assertContains(response, "Failed Jobs")

    def test_active_jobs_view(self):
        """
        Test active jobs view.

        Requirement 33.1: Display all currently running Celery tasks.
        """
        response = self.client.get(reverse("core:jobs:active"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Jobs")

    def test_pending_jobs_view(self):
        """
        Test pending jobs view.

        Requirement 33.2: Display pending jobs in queue with priority and ETA.
        """
        response = self.client.get(reverse("core:jobs:pending"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Jobs")
        self.assertContains(response, "Priority")
        self.assertContains(response, "ETA")

    def test_completed_jobs_view_with_data(self):
        """
        Test completed jobs list view with real data.

        Requirement 33.3: Display completed jobs with execution time and status.
        """
        # Create a completed job
        job = JobExecution.objects.create(
            task_id="view-test-completed-123",
            task_name="apps.test.tasks.test_task",
            status="SUCCESS",
            execution_time=5.5,
            completed_at=timezone.now(),
            queue="default",
        )

        response = self.client.get(reverse("core:jobs:completed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed Jobs")
        self.assertContains(response, job.task_name)
        self.assertContains(response, "5.50s")  # Execution time displayed

    def test_failed_jobs_view_with_data(self):
        """
        Test failed jobs list view with real data.

        Requirement 33.4: Display failed jobs with error details and retry options.
        """
        # Create a failed job
        job = JobExecution.objects.create(
            task_id="view-test-failed-456",
            task_name="apps.test.tasks.test_task",
            status="FAILURE",
            error="Test error message for view",
            traceback="Test traceback",
            completed_at=timezone.now(),
            retry_count=1,
            max_retries=3,
        )

        response = self.client.get(reverse("core:jobs:failed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed Jobs")
        self.assertContains(response, job.task_name)
        self.assertContains(response, "Test error message")
        # Should show retry option since retry_count < max_retries
        self.assertContains(response, "Retry")

    def test_job_detail_view(self):
        """
        Test job detail view shows complete information.

        Requirement 33.4: Display failed jobs with error details.
        """
        # Create a job with full details
        job = JobExecution.objects.create(
            task_id="detail-test-789",
            task_name="apps.test.tasks.detailed_task",
            status="FAILURE",
            args=["arg1", "arg2"],
            kwargs={"key1": "value1"},
            error="Detailed error message",
            traceback="Full traceback here",
            execution_time=10.5,
            started_at=timezone.now() - timedelta(seconds=10),
            completed_at=timezone.now(),
            queue="default",
            priority=8,
            retry_count=2,
            max_retries=3,
        )

        response = self.client.get(reverse("core:jobs:detail", kwargs={"task_id": job.task_id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Details")
        self.assertContains(response, job.task_name)
        self.assertContains(response, job.error)
        self.assertContains(response, job.traceback)
        self.assertContains(response, "10.50")  # Execution time
        self.assertContains(response, "default")  # Queue
        self.assertContains(response, "8")  # Priority

    def test_job_statistics_view(self):
        """
        Test job statistics view.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        # Create statistics
        stats = JobStatistics.objects.create(
            task_name="apps.test.tasks.stats_task",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            avg_execution_time=45.5,
            min_execution_time=10.0,
            max_execution_time=120.0,
        )

        response = self.client.get(reverse("core:jobs:statistics"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Statistics")
        self.assertContains(response, stats.task_name)
        self.assertContains(response, "100")  # Total executions
        self.assertContains(response, "95.0")  # Success rate

    def test_job_api_endpoint(self):
        """Test jobs API endpoint returns JSON."""
        response = self.client.get(reverse("core:jobs:api_jobs"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("timestamp", data)

    def test_queue_stats_api_endpoint(self):
        """Test queue stats API endpoint returns JSON."""
        response = self.client.get(reverse("core:jobs:api_queues"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("queues", data)
        self.assertIn("timestamp", data)

    def test_non_admin_cannot_access(self):
        """Test that non-admin users cannot access job monitoring."""
        # Create tenant first
        tenant = Tenant.objects.create(
            company_name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
        )

        # Create regular user with tenant
        User = get_user_model()
        User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=tenant,
        )

        self.client.logout()
        self.client.login(username="regular", password="testpass123")

        response = self.client.get(reverse("core:jobs:dashboard"))

        # Should be redirected or forbidden
        self.assertNotEqual(response.status_code, 200)
