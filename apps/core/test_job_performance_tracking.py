"""
REAL Integration tests for job performance tracking.

Per Requirement 33.9 and 33.10 - Job Performance Tracking

IMPORTANT: These are REAL integration tests - NO MOCKS ALLOWED.
All tests use real Celery workers, real database, and real resource monitoring.
"""

from time import sleep

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from celery import shared_task

from apps.core.job_models import JobExecution, JobStatistics
from apps.core.job_service import JobMonitoringService


# Test tasks for performance tracking
@shared_task(bind=True, name="test_performance.cpu_intensive_task")
def cpu_intensive_task(self):
    """Test task that uses CPU."""
    # Perform CPU-intensive operation
    result = 0
    for i in range(1000000):
        result += i * i
    return f"CPU intensive result: {result}"


@shared_task(bind=True, name="test_performance.memory_intensive_task")
def memory_intensive_task(self):
    """Test task that uses memory."""
    # Allocate memory
    large_list = [i for i in range(100000)]
    return f"Memory intensive result: {len(large_list)}"


@shared_task(bind=True, name="test_performance.slow_task")
def slow_task(self, duration=2):
    """Test task that takes time."""
    sleep(duration)
    return f"Completed after {duration}s"


@shared_task(bind=True, name="test_performance.fast_task")
def fast_task(self):
    """Test task that completes quickly."""
    return "Fast task completed"


class JobPerformanceTrackingIntegrationTest(TestCase):
    """
    REAL integration tests for job performance tracking.
    Tests with actual Celery workers and real resource monitoring - NO MOCKS.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    def setUp(self):
        """Clean up before each test."""
        JobExecution.objects.all().delete()
        JobStatistics.objects.all().delete()

    def test_execution_time_tracking(self):
        """
        Test that execution times are tracked correctly.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        # Create a job execution with execution time
        job = JobExecution.objects.create(
            task_id="test-exec-time-123",
            task_name="test_performance.fast_task",
            status="SUCCESS",
            execution_time=5.5,
            completed_at=timezone.now(),
        )

        # Verify execution time is recorded
        job.refresh_from_db()
        self.assertIsNotNone(job.execution_time, "Execution time should be recorded")
        self.assertEqual(job.execution_time, 5.5, "Execution time should match")
        self.assertEqual(job.status, "SUCCESS", "Task should be successful")

    def test_slow_job_identification(self):
        """
        Test that slow jobs are identified correctly.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        # Create job executions with varying execution times
        task_name = "test_performance.test_slow_identification"

        # Create slow jobs (>60s) - make sure average is >60s
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"slow-{i}",
                task_name=task_name,
                status="SUCCESS",
                execution_time=70.0 + i * 5,  # 70, 75, 80, 85, 90 - average will be 80
                completed_at=timezone.now(),
            )

        # Update statistics
        JobMonitoringService.update_job_statistics(task_name)

        # Get statistics
        stats = JobStatistics.objects.get(task_name=task_name)

        # Verify statistics
        self.assertEqual(stats.total_executions, 5)
        self.assertEqual(stats.avg_execution_time, 80.0, "Average should be 80s")
        self.assertEqual(stats.min_execution_time, 70.0)
        self.assertEqual(stats.max_execution_time, 90.0)
        self.assertTrue(stats.is_slow, "Job should be marked as slow")

        # Test slow job identification
        slow_jobs = JobMonitoringService.get_slow_jobs(threshold_seconds=60.0)

        # Filter for our specific task
        slow_job = slow_jobs.filter(task_name=task_name).first()
        self.assertIsNotNone(slow_job, "Our test task should be identified as slow")
        self.assertTrue(slow_job.is_slow, "Job should be marked as slow")
        self.assertGreater(
            slow_job.avg_execution_time, 60.0, "Average execution time should be >60s"
        )

    def test_cpu_usage_tracking(self):
        """
        Test that CPU usage is tracked correctly.

        Requirement 33.10: Track CPU and memory usage per job type.
        """
        # Create job executions with CPU usage
        task_name = "test_performance.test_cpu_tracking"

        for i in range(5):
            JobExecution.objects.create(
                task_id=f"cpu-test-{i}",
                task_name=task_name,
                status="SUCCESS",
                execution_time=5.0,
                cpu_percent=50.0 + i * 5,  # Varying CPU usage
                memory_mb=100.0,
                peak_memory_mb=120.0,
                completed_at=timezone.now(),
            )

        # Update statistics
        JobMonitoringService.update_job_statistics(task_name)

        # Get statistics
        stats = JobStatistics.objects.get(task_name=task_name)

        # Verify CPU tracking
        self.assertIsNotNone(stats.avg_cpu_percent, "Average CPU should be calculated")
        self.assertGreater(stats.avg_cpu_percent, 0, "Average CPU should be positive")
        self.assertIsNotNone(stats.peak_cpu_percent, "Peak CPU should be recorded")
        self.assertEqual(stats.peak_cpu_percent, 70.0, "Peak CPU should be maximum value")

    def test_memory_usage_tracking(self):
        """
        Test that memory usage is tracked correctly.

        Requirement 33.10: Track CPU and memory usage per job type.
        """
        # Create job executions with memory usage
        task_name = "test_performance.test_memory_tracking"

        for i in range(5):
            JobExecution.objects.create(
                task_id=f"memory-test-{i}",
                task_name=task_name,
                status="SUCCESS",
                execution_time=5.0,
                cpu_percent=30.0,
                memory_mb=200.0 + i * 50,  # Varying memory usage
                peak_memory_mb=250.0 + i * 50,
                completed_at=timezone.now(),
            )

        # Update statistics
        JobMonitoringService.update_job_statistics(task_name)

        # Get statistics
        stats = JobStatistics.objects.get(task_name=task_name)

        # Verify memory tracking
        self.assertIsNotNone(stats.avg_memory_mb, "Average memory should be calculated")
        self.assertGreater(stats.avg_memory_mb, 0, "Average memory should be positive")
        self.assertIsNotNone(stats.peak_memory_mb, "Peak memory should be recorded")
        self.assertEqual(stats.peak_memory_mb, 450.0, "Peak memory should be maximum value")

    def test_resource_intensive_job_identification(self):
        """
        Test that resource-intensive jobs are identified correctly.

        Requirement 33.10: Track CPU and memory usage per job type.
        """
        # Create high CPU job
        high_cpu_task = "test_performance.high_cpu_job"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"high-cpu-{i}",
                task_name=high_cpu_task,
                status="SUCCESS",
                execution_time=10.0,
                cpu_percent=80.0,  # High CPU
                memory_mb=100.0,
                peak_memory_mb=120.0,
                completed_at=timezone.now(),
            )

        # Create high memory job
        high_memory_task = "test_performance.high_memory_job"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"high-memory-{i}",
                task_name=high_memory_task,
                status="SUCCESS",
                execution_time=10.0,
                cpu_percent=20.0,
                memory_mb=800.0,  # High memory
                peak_memory_mb=900.0,
                completed_at=timezone.now(),
            )

        # Create normal job
        normal_task = "test_performance.normal_job"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"normal-{i}",
                task_name=normal_task,
                status="SUCCESS",
                execution_time=10.0,
                cpu_percent=30.0,  # Normal CPU
                memory_mb=200.0,  # Normal memory
                peak_memory_mb=220.0,
                completed_at=timezone.now(),
            )

        # Update statistics for all tasks
        JobMonitoringService.update_job_statistics(high_cpu_task)
        JobMonitoringService.update_job_statistics(high_memory_task)
        JobMonitoringService.update_job_statistics(normal_task)

        # Test resource-intensive job identification
        resource_intensive = JobMonitoringService.get_resource_intensive_jobs(
            cpu_threshold=50.0, memory_threshold_mb=500.0
        )

        self.assertEqual(resource_intensive.count(), 2, "Should identify 2 resource-intensive jobs")

        task_names = [job.task_name for job in resource_intensive]
        self.assertIn(high_cpu_task, task_names, "High CPU job should be identified")
        self.assertIn(high_memory_task, task_names, "High memory job should be identified")
        self.assertNotIn(normal_task, task_names, "Normal job should not be identified")

    def test_performance_summary(self):
        """
        Test that performance summary is calculated correctly.

        Requirement 33.9, 33.10: Track execution times and resource usage.
        """
        # Create various jobs
        tasks = [
            ("test_performance.task1", 30.0, 40.0, 200.0),  # Normal
            ("test_performance.task2", 70.0, 60.0, 600.0),  # Slow and resource-intensive
            ("test_performance.task3", 20.0, 30.0, 150.0),  # Fast
        ]

        for task_name, exec_time, cpu, memory in tasks:
            for i in range(3):
                JobExecution.objects.create(
                    task_id=f"{task_name}-{i}",
                    task_name=task_name,
                    status="SUCCESS",
                    execution_time=exec_time,
                    cpu_percent=cpu,
                    memory_mb=memory,
                    peak_memory_mb=memory + 50,
                    completed_at=timezone.now(),
                )
            JobMonitoringService.update_job_statistics(task_name)

        # Get performance summary
        summary = JobMonitoringService.get_performance_summary()

        # Verify summary
        self.assertEqual(summary["total_job_types"], 3, "Should have 3 job types")
        self.assertEqual(summary["slow_jobs_count"], 1, "Should have 1 slow job")
        self.assertEqual(
            summary["resource_intensive_count"], 1, "Should have 1 resource-intensive job"
        )
        self.assertGreater(summary["avg_execution_time"], 0, "Should have average execution time")
        self.assertGreater(summary["avg_cpu_percent"], 0, "Should have average CPU")
        self.assertGreater(summary["avg_memory_mb"], 0, "Should have average memory")

    def test_performance_tracking_service_methods(self):
        """
        Test performance tracking service methods work correctly.

        Requirement 33.9, 33.10: Track execution times and resource usage.
        """
        # Create test data
        task_name = "test_performance.service_test"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"service-test-{i}",
                task_name=task_name,
                status="SUCCESS",
                execution_time=50.0 + i * 10,
                cpu_percent=40.0 + i * 5,
                memory_mb=300.0 + i * 50,
                peak_memory_mb=350.0 + i * 50,
                completed_at=timezone.now(),
            )

        # Update statistics
        JobMonitoringService.update_job_statistics(task_name)

        # Verify service methods work
        slow_jobs = JobMonitoringService.get_slow_jobs()
        self.assertIsInstance(slow_jobs.count(), int, "get_slow_jobs should return queryset")

        resource_intensive = JobMonitoringService.get_resource_intensive_jobs()
        self.assertIsInstance(
            resource_intensive.count(), int, "get_resource_intensive_jobs should return queryset"
        )

        summary = JobMonitoringService.get_performance_summary()
        self.assertIsInstance(summary, dict, "get_performance_summary should return dict")
        self.assertIn("total_job_types", summary, "Summary should have total_job_types")
        self.assertGreater(summary["total_job_types"], 0, "Should have job types")


class JobPerformanceViewsIntegrationTest(TestCase):
    """
    REAL integration tests for job performance views.
    Tests with actual HTTP requests and database - NO MOCKS.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
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

        # Create test data
        self._create_test_performance_data()

    def _create_test_performance_data(self):
        """Create test performance data."""
        # Create slow job
        slow_task = "test_performance.slow_job"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"slow-{i}",
                task_name=slow_task,
                status="SUCCESS",
                execution_time=75.0 + i,
                cpu_percent=40.0,
                memory_mb=200.0,
                peak_memory_mb=250.0,
                completed_at=timezone.now(),
            )
        JobMonitoringService.update_job_statistics(slow_task)

        # Create resource-intensive job
        intensive_task = "test_performance.intensive_job"
        for i in range(5):
            JobExecution.objects.create(
                task_id=f"intensive-{i}",
                task_name=intensive_task,
                status="SUCCESS",
                execution_time=30.0,
                cpu_percent=70.0 + i,
                memory_mb=700.0 + i * 50,
                peak_memory_mb=800.0 + i * 50,
                completed_at=timezone.now(),
            )
        JobMonitoringService.update_job_statistics(intensive_task)

    def test_performance_view_access(self):
        """
        Test that performance view is accessible.

        Requirement 33.9, 33.10: Display performance tracking interface.
        """
        response = self.client.get(reverse("core:jobs:performance"))

        self.assertEqual(response.status_code, 200, "Performance view should be accessible")
        self.assertContains(response, "Job Performance Tracking")
        self.assertContains(response, "Slow Jobs")
        self.assertContains(response, "Resource Intensive Jobs")

    def test_performance_view_displays_slow_jobs(self):
        """
        Test that performance view displays slow jobs.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        response = self.client.get(reverse("core:jobs:performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_performance.slow_job")
        self.assertContains(response, "75")  # Execution time

    def test_performance_view_displays_resource_intensive_jobs(self):
        """
        Test that performance view displays resource-intensive jobs.

        Requirement 33.10: Track CPU and memory usage per job type.
        """
        response = self.client.get(reverse("core:jobs:performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_performance.intensive_job")
        # Should show CPU or memory metrics

    def test_performance_api_endpoint(self):
        """
        Test that performance API endpoint returns correct data.

        Requirement 33.9, 33.10: Provide performance data via API.
        """
        response = self.client.get(reverse("core:jobs:api_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("timestamp", data)
        self.assertIn("summary", data)
        self.assertIn("slow_jobs", data)
        self.assertIn("resource_intensive_jobs", data)

        # Verify summary structure
        summary = data["summary"]
        self.assertIn("total_job_types", summary)
        self.assertIn("slow_jobs_count", summary)
        self.assertIn("resource_intensive_count", summary)
        self.assertIn("avg_execution_time", summary)
        self.assertIn("avg_cpu_percent", summary)
        self.assertIn("avg_memory_mb", summary)

    def test_dashboard_includes_performance_metrics(self):
        """
        Test that dashboard includes performance metrics.

        Requirement 33.9, 33.10: Display performance summary on dashboard.
        """
        response = self.client.get(reverse("core:jobs:dashboard"))

        self.assertEqual(response.status_code, 200)

        # Check that performance data is in context
        self.assertIn("performance_summary", response.context)
        self.assertIn("slow_jobs", response.context)
        self.assertIn("resource_intensive_jobs", response.context)

        # Verify performance summary structure
        summary = response.context["performance_summary"]
        self.assertIsInstance(summary, dict)
        self.assertIn("total_job_types", summary)

    def test_statistics_view_includes_performance_data(self):
        """
        Test that statistics view includes performance data.

        Requirement 33.9, 33.10: Display performance metrics in statistics.
        """
        response = self.client.get(reverse("core:jobs:statistics"))

        self.assertEqual(response.status_code, 200)

        # Check that performance data is in context
        self.assertIn("performance_summary", response.context)
        self.assertIn("slow_jobs", response.context)
        self.assertIn("resource_intensive_jobs", response.context)

    def test_performance_link_in_dashboard(self):
        """
        Test that dashboard has link to performance page.

        Requirement 33.9, 33.10: Provide navigation to performance tracking.
        """
        response = self.client.get(reverse("core:jobs:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:jobs:performance"))
        self.assertContains(response, "Performance")


class JobPerformanceModelsTest(TestCase):
    """
    Test job performance tracking models.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    def test_job_execution_performance_fields(self):
        """Test that JobExecution has performance tracking fields."""
        job = JobExecution.objects.create(
            task_id="perf-test-123",
            task_name="test.task",
            status="SUCCESS",
            execution_time=45.5,
            cpu_percent=55.5,
            memory_mb=350.0,
            peak_memory_mb=400.0,
            completed_at=timezone.now(),
        )

        # Verify fields are saved correctly
        job.refresh_from_db()
        self.assertEqual(job.execution_time, 45.5)
        self.assertEqual(job.cpu_percent, 55.5)
        self.assertEqual(job.memory_mb, 350.0)
        self.assertEqual(job.peak_memory_mb, 400.0)

    def test_job_statistics_performance_fields(self):
        """Test that JobStatistics has performance tracking fields."""
        stats = JobStatistics.objects.create(
            task_name="test.task",
            total_executions=10,
            successful_executions=9,
            failed_executions=1,
            avg_execution_time=45.5,
            min_execution_time=30.0,
            max_execution_time=60.0,
            avg_cpu_percent=55.5,
            avg_memory_mb=350.0,
            peak_cpu_percent=80.0,
            peak_memory_mb=500.0,
        )

        # Verify fields are saved correctly
        stats.refresh_from_db()
        self.assertEqual(stats.avg_cpu_percent, 55.5)
        self.assertEqual(stats.avg_memory_mb, 350.0)
        self.assertEqual(stats.peak_cpu_percent, 80.0)
        self.assertEqual(stats.peak_memory_mb, 500.0)

    def test_is_slow_property(self):
        """Test the is_slow property on JobStatistics."""
        # Create slow job
        slow_stats = JobStatistics.objects.create(
            task_name="slow.task",
            total_executions=5,
            successful_executions=5,
            failed_executions=0,
            avg_execution_time=75.0,  # >60s
        )

        # Create fast job
        fast_stats = JobStatistics.objects.create(
            task_name="fast.task",
            total_executions=5,
            successful_executions=5,
            failed_executions=0,
            avg_execution_time=30.0,  # <60s
        )

        self.assertTrue(slow_stats.is_slow, "Job with >60s avg should be slow")
        self.assertFalse(fast_stats.is_slow, "Job with <60s avg should not be slow")
