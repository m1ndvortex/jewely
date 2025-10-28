"""
Job monitoring service for Celery task management.

This module provides services for:
- Fetching active, pending, and completed jobs
- Job statistics calculation
- Job retry and cancellation

Per Requirement 33 - Scheduled Job Management
"""

from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from celery.app.control import Inspect
from celery.result import AsyncResult

from apps.core.job_models import JobExecution, JobStatistics
from config.celery import app


class JobMonitoringService:
    """
    Service for monitoring and managing Celery jobs.

    Requirement 33.1: Display all currently running Celery tasks.
    Requirement 33.2: Display pending jobs in queue with priority and ETA.
    Requirement 33.3: Display completed jobs with execution time and status.
    Requirement 33.4: Display failed jobs with error details and retry options.
    """

    @staticmethod
    def get_active_jobs() -> List[Dict]:
        """
        Get all currently running Celery tasks.

        Requirement 33.1: Display all currently running Celery tasks.
        """
        try:
            inspect = Inspect(app=app)
            active_tasks = inspect.active()

            if not active_tasks:
                return []

            jobs = []
            for worker_name, tasks in active_tasks.items():
                for task in tasks:
                    jobs.append(
                        {
                            "task_id": task.get("id"),
                            "task_name": task.get("name"),
                            "worker": worker_name,
                            "args": task.get("args", []),
                            "kwargs": task.get("kwargs", {}),
                            "time_start": task.get("time_start"),
                            "status": "RUNNING",
                        }
                    )

            return jobs
        except Exception:
            return []

    @staticmethod
    def get_pending_jobs() -> List[Dict]:
        """
        Get all pending jobs in queue.

        Requirement 33.2: Display pending jobs in queue with priority and ETA.
        """
        try:
            inspect = Inspect(app=app)

            # Get reserved tasks (tasks in queue but not yet started)
            reserved_tasks = inspect.reserved()
            scheduled_tasks = inspect.scheduled()

            jobs = []

            # Process reserved tasks
            if reserved_tasks:
                for worker_name, tasks in reserved_tasks.items():
                    for task in tasks:
                        jobs.append(
                            {
                                "task_id": task.get("id"),
                                "task_name": task.get("name"),
                                "worker": worker_name,
                                "args": task.get("args", []),
                                "kwargs": task.get("kwargs", {}),
                                "priority": task.get("delivery_info", {}).get("priority", 5),
                                "eta": None,
                                "status": "PENDING",
                            }
                        )

            # Process scheduled tasks
            if scheduled_tasks:
                for worker_name, tasks in scheduled_tasks.items():
                    for task in tasks:
                        eta = task.get("eta")
                        jobs.append(
                            {
                                "task_id": task.get("request", {}).get("id"),
                                "task_name": task.get("request", {}).get("name"),
                                "worker": worker_name,
                                "args": task.get("request", {}).get("args", []),
                                "kwargs": task.get("request", {}).get("kwargs", {}),
                                "priority": task.get("request", {})
                                .get("delivery_info", {})
                                .get("priority", 5),
                                "eta": eta,
                                "status": "SCHEDULED",
                            }
                        )

            # Sort by priority (higher priority first)
            jobs.sort(key=lambda x: x.get("priority", 5), reverse=True)

            return jobs
        except Exception:
            return []

    @staticmethod
    def get_completed_jobs(limit: int = 100) -> List[JobExecution]:
        """
        Get recently completed jobs.

        Requirement 33.3: Display completed jobs with execution time and status.
        """
        return JobExecution.objects.filter(status__in=["SUCCESS", "FAILURE", "REVOKED"]).order_by(
            "-completed_at"
        )[:limit]

    @staticmethod
    def get_failed_jobs(limit: int = 100) -> List[JobExecution]:
        """
        Get failed jobs with error details.

        Requirement 33.4: Display failed jobs with error details and retry options.
        """
        return JobExecution.objects.filter(status="FAILURE").order_by("-completed_at")[:limit]

    @staticmethod
    def get_job_by_id(task_id: str) -> Optional[Dict]:
        """Get job details by task ID."""
        # First check database
        try:
            job_execution = JobExecution.objects.get(task_id=task_id)
            return {
                "task_id": job_execution.task_id,
                "task_name": job_execution.task_name,
                "status": job_execution.status,
                "args": job_execution.args,
                "kwargs": job_execution.kwargs,
                "queued_at": job_execution.queued_at,
                "started_at": job_execution.started_at,
                "completed_at": job_execution.completed_at,
                "execution_time": job_execution.execution_time,
                "result": job_execution.result,
                "error": job_execution.error,
                "traceback": job_execution.traceback,
                "retry_count": job_execution.retry_count,
                "can_retry": job_execution.can_retry,
                "source": "database",
            }
        except JobExecution.DoesNotExist:
            pass

        # Check Celery result backend
        try:
            result = AsyncResult(task_id, app=app)
            return {
                "task_id": task_id,
                "task_name": result.name or "Unknown",
                "status": result.state,
                "result": str(result.result) if result.result else None,
                "error": str(result.info) if result.failed() else None,
                "source": "celery",
            }
        except Exception:
            return None

    @staticmethod
    def retry_job(task_id: str) -> bool:
        """
        Retry a failed job.

        Requirement 33.4: Display failed jobs with retry options.
        """
        try:
            job_execution = JobExecution.objects.get(task_id=task_id)

            if not job_execution.can_retry:
                return False

            # Get the task function
            task_func = app.tasks.get(job_execution.task_name)
            if not task_func:
                return False

            # Retry the task
            new_result = task_func.apply_async(
                args=job_execution.args,
                kwargs=job_execution.kwargs,
                queue=job_execution.queue,
                priority=job_execution.priority,
            )

            # Update retry count
            job_execution.retry_count += 1
            job_execution.status = "RETRY"
            job_execution.save()

            # Create new execution record
            JobExecution.objects.create(
                task_id=new_result.id,
                task_name=job_execution.task_name,
                args=job_execution.args,
                kwargs=job_execution.kwargs,
                queue=job_execution.queue,
                priority=job_execution.priority,
                retry_count=job_execution.retry_count,
                max_retries=job_execution.max_retries,
            )

            return True
        except Exception:
            return False

    @staticmethod
    def cancel_job(task_id: str) -> bool:
        """
        Cancel a pending or running job.

        Requirement 33.8: Allow administrators to cancel running or pending jobs.
        """
        try:
            # Revoke the task
            app.control.revoke(task_id, terminate=True)

            # Update database record if exists
            try:
                job_execution = JobExecution.objects.get(task_id=task_id)
                job_execution.status = "REVOKED"
                job_execution.completed_at = timezone.now()
                job_execution.save()
            except JobExecution.DoesNotExist:
                pass

            return True
        except Exception:
            return False

    @staticmethod
    def get_job_statistics() -> List[JobStatistics]:
        """
        Get statistics for all job types.

        Requirement 33.9: Track execution times and identify slow jobs.
        """
        return JobStatistics.objects.all().order_by("-total_executions")

    @staticmethod
    def update_job_statistics(task_name: str):
        """Update statistics for a specific job type."""
        # Get all executions for this task
        executions = JobExecution.objects.filter(task_name=task_name)

        if not executions.exists():
            return

        # Calculate statistics
        stats = executions.aggregate(
            total=Count("id"),
            successful=Count("id", filter=Q(status="SUCCESS")),
            failed=Count("id", filter=Q(status="FAILURE")),
            avg_time=Avg("execution_time", filter=Q(execution_time__isnull=False)),
            min_time=Min("execution_time", filter=Q(execution_time__isnull=False)),
            max_time=Max("execution_time", filter=Q(execution_time__isnull=False)),
        )

        # Get last execution
        last_execution = executions.order_by("-completed_at").first()

        # Update or create statistics
        JobStatistics.objects.update_or_create(
            task_name=task_name,
            defaults={
                "total_executions": stats["total"],
                "successful_executions": stats["successful"],
                "failed_executions": stats["failed"],
                "avg_execution_time": stats["avg_time"] or 0.0,
                "min_execution_time": stats["min_time"],
                "max_execution_time": stats["max_time"],
                "last_execution_at": last_execution.completed_at if last_execution else None,
                "last_execution_status": last_execution.status if last_execution else None,
            },
        )

    @staticmethod
    def cleanup_old_executions(days: int = 30):
        """Clean up old job execution records."""
        cutoff_date = timezone.now() - timedelta(days=days)
        JobExecution.objects.filter(completed_at__lt=cutoff_date).delete()

    @staticmethod
    def get_queue_stats() -> Dict:  # noqa: C901
        """Get statistics for all queues."""
        try:
            inspect = Inspect(app=app)

            # Get active and reserved tasks
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            scheduled = inspect.scheduled() or {}

            # Count tasks per queue
            queue_stats = {}

            # Count active tasks
            for worker_tasks in active.values():
                for task in worker_tasks:
                    queue = task.get("delivery_info", {}).get("routing_key", "default")
                    if queue not in queue_stats:
                        queue_stats[queue] = {"active": 0, "pending": 0, "scheduled": 0}
                    queue_stats[queue]["active"] += 1

            # Count reserved tasks
            for worker_tasks in reserved.values():
                for task in worker_tasks:
                    queue = task.get("delivery_info", {}).get("routing_key", "default")
                    if queue not in queue_stats:
                        queue_stats[queue] = {"active": 0, "pending": 0, "scheduled": 0}
                    queue_stats[queue]["pending"] += 1

            # Count scheduled tasks
            for worker_tasks in scheduled.values():
                for task in worker_tasks:
                    queue = (
                        task.get("request", {})
                        .get("delivery_info", {})
                        .get("routing_key", "default")
                    )
                    if queue not in queue_stats:
                        queue_stats[queue] = {"active": 0, "pending": 0, "scheduled": 0}
                    queue_stats[queue]["scheduled"] += 1

            return queue_stats
        except Exception:
            return {}
