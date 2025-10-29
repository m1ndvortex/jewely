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
        """
        Update statistics for a specific job type.

        Requirement 33.9: Track execution times and identify slow jobs.
        Requirement 33.10: Track CPU and memory usage per job type.
        """
        # Get all executions for this task
        executions = JobExecution.objects.filter(task_name=task_name)

        if not executions.exists():
            return

        # Calculate statistics including resource usage
        stats = executions.aggregate(
            total=Count("id"),
            successful=Count("id", filter=Q(status="SUCCESS")),
            failed=Count("id", filter=Q(status="FAILURE")),
            avg_time=Avg("execution_time", filter=Q(execution_time__isnull=False)),
            min_time=Min("execution_time", filter=Q(execution_time__isnull=False)),
            max_time=Max("execution_time", filter=Q(execution_time__isnull=False)),
            avg_cpu=Avg("cpu_percent", filter=Q(cpu_percent__isnull=False)),
            avg_memory=Avg("memory_mb", filter=Q(memory_mb__isnull=False)),
            peak_cpu=Max("cpu_percent", filter=Q(cpu_percent__isnull=False)),
            peak_memory=Max("peak_memory_mb", filter=Q(peak_memory_mb__isnull=False)),
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
                "avg_cpu_percent": stats["avg_cpu"],
                "avg_memory_mb": stats["avg_memory"],
                "peak_cpu_percent": stats["peak_cpu"],
                "peak_memory_mb": stats["peak_memory"],
                "last_execution_at": last_execution.completed_at if last_execution else None,
                "last_execution_status": last_execution.status if last_execution else None,
            },
        )

    @staticmethod
    def get_slow_jobs(threshold_seconds: float = 60.0) -> List[JobStatistics]:
        """
        Get jobs that are considered slow.

        Requirement 33.9: Track execution times and identify slow jobs.

        Args:
            threshold_seconds: Jobs with avg execution time above this are considered slow

        Returns:
            List of JobStatistics for slow jobs
        """
        return JobStatistics.objects.filter(avg_execution_time__gt=threshold_seconds).order_by(
            "-avg_execution_time"
        )

    @staticmethod
    def get_resource_intensive_jobs(
        cpu_threshold: float = 50.0, memory_threshold_mb: float = 500.0
    ) -> List[JobStatistics]:
        """
        Get jobs that are resource-intensive.

        Requirement 33.10: Track CPU and memory usage per job type.

        Args:
            cpu_threshold: Jobs with avg CPU above this percentage are considered intensive
            memory_threshold_mb: Jobs with avg memory above this MB are considered intensive

        Returns:
            List of JobStatistics for resource-intensive jobs
        """
        return JobStatistics.objects.filter(
            Q(avg_cpu_percent__gt=cpu_threshold) | Q(avg_memory_mb__gt=memory_threshold_mb)
        ).order_by("-avg_cpu_percent", "-avg_memory_mb")

    @staticmethod
    def get_performance_summary() -> Dict:
        """
        Get overall performance summary across all jobs.

        Requirement 33.9, 33.10: Track execution times and resource usage.

        Returns:
            Dictionary with performance metrics
        """
        all_stats = JobStatistics.objects.all()

        if not all_stats.exists():
            return {
                "total_job_types": 0,
                "slow_jobs_count": 0,
                "resource_intensive_count": 0,
                "avg_execution_time": 0.0,
                "avg_cpu_percent": 0.0,
                "avg_memory_mb": 0.0,
            }

        summary = all_stats.aggregate(
            avg_time=Avg("avg_execution_time"),
            avg_cpu=Avg("avg_cpu_percent", filter=Q(avg_cpu_percent__isnull=False)),
            avg_memory=Avg("avg_memory_mb", filter=Q(avg_memory_mb__isnull=False)),
        )

        slow_jobs = all_stats.filter(avg_execution_time__gt=60.0).count()
        resource_intensive = all_stats.filter(
            Q(avg_cpu_percent__gt=50.0) | Q(avg_memory_mb__gt=500.0)
        ).count()

        return {
            "total_job_types": all_stats.count(),
            "slow_jobs_count": slow_jobs,
            "resource_intensive_count": resource_intensive,
            "avg_execution_time": summary["avg_time"] or 0.0,
            "avg_cpu_percent": summary["avg_cpu"] or 0.0,
            "avg_memory_mb": summary["avg_memory"] or 0.0,
        }

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


class JobManagementService:
    """
    Service for managing Celery jobs.

    Requirement 33.5: Allow administrators to manually trigger scheduled jobs.
    Requirement 33.6: Allow administrators to configure job schedules.
    Requirement 33.7: Allow administrators to set job priorities.
    """

    @staticmethod
    def trigger_job(
        task_name: str,
        args: list = None,
        kwargs: dict = None,
        queue: str = "default",
        priority: int = 5,
        countdown: int = None,
    ) -> Optional[str]:
        """
        Manually trigger a job.

        Requirement 33.5: Allow administrators to manually trigger scheduled jobs.

        Args:
            task_name: Name of the Celery task
            args: Task arguments
            kwargs: Task keyword arguments
            queue: Queue name
            priority: Priority level (0-10)
            countdown: Delay before execution in seconds

        Returns:
            Task ID if successful, None otherwise
        """
        try:
            task_func = app.tasks.get(task_name)
            if not task_func:
                return None

            # Trigger the task
            result = task_func.apply_async(
                args=args or [],
                kwargs=kwargs or {},
                queue=queue,
                priority=priority,
                countdown=countdown,
            )

            # Create execution record
            JobExecution.objects.create(
                task_id=result.id,
                task_name=task_name,
                args=args or [],
                kwargs=kwargs or {},
                queue=queue,
                priority=priority,
                status="PENDING",
            )

            return result.id
        except Exception:
            return None

    @staticmethod
    def create_schedule(
        name: str,
        task_name: str,
        schedule_type: str,
        cron_expression: str = None,
        interval_value: int = None,
        interval_unit: str = None,
        args: list = None,
        kwargs: dict = None,
        queue: str = "default",
        priority: int = 5,
        enabled: bool = True,
        created_by=None,
    ):
        """
        Create a job schedule.

        Requirement 33.6: Allow administrators to configure job schedules.

        Returns:
            JobSchedule instance if successful, None otherwise
        """
        try:
            from apps.core.job_models import JobSchedule

            schedule = JobSchedule.objects.create(
                name=name,
                task_name=task_name,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                interval_value=interval_value,
                interval_unit=interval_unit,
                args=args or [],
                kwargs=kwargs or {},
                queue=queue,
                priority=priority,
                enabled=enabled,
                created_by=created_by,
            )

            return schedule
        except Exception:
            return None

    @staticmethod
    def update_schedule(schedule_id: int, **updates) -> bool:  # noqa: C901
        """
        Update a job schedule.

        Requirement 33.6: Allow administrators to configure job schedules.

        Args:
            schedule_id: ID of the schedule to update
            **updates: Fields to update (task_name, schedule_type, cron_expression,
                      interval_value, interval_unit, args, kwargs, queue, priority, enabled)

        Returns:
            True if successful, False otherwise
        """
        try:
            from apps.core.job_models import JobSchedule

            schedule = JobSchedule.objects.get(pk=schedule_id)

            # Update fields that are provided
            for field, value in updates.items():
                if value is not None and hasattr(schedule, field):
                    setattr(schedule, field, value)

            schedule.save()
            return True
        except Exception:
            return False

    @staticmethod
    def delete_schedule(schedule_id: int) -> bool:
        """
        Delete a job schedule.

        Requirement 33.6: Allow administrators to configure job schedules.

        Returns:
            True if successful, False otherwise
        """
        try:
            from apps.core.job_models import JobSchedule

            schedule = JobSchedule.objects.get(pk=schedule_id)
            schedule.delete()
            return True
        except Exception:
            return False

    @staticmethod
    def update_job_priority(task_id: str, priority: int, queue: str = None) -> bool:
        """
        Update job priority.

        Requirement 33.7: Allow administrators to set job priorities.

        Note: This updates the database record. For running tasks, priority
        cannot be changed. For pending tasks, they would need to be revoked
        and resubmitted with new priority (only if task exists in Celery registry).

        Returns:
            True if successful, False otherwise
        """
        try:
            job_execution = JobExecution.objects.get(task_id=task_id)

            # Update priority in database
            job_execution.priority = priority
            if queue:
                job_execution.queue = queue
            job_execution.save()

            # If job is pending, try to revoke and resubmit with new priority
            if job_execution.status == "PENDING":
                # Get the task function
                task_func = app.tasks.get(job_execution.task_name)
                if task_func:
                    try:
                        # Revoke old task
                        app.control.revoke(task_id)

                        # Resubmit with new priority
                        new_result = task_func.apply_async(
                            args=job_execution.args,
                            kwargs=job_execution.kwargs,
                            queue=queue or job_execution.queue,
                            priority=priority,
                        )

                        # Update task_id
                        job_execution.task_id = new_result.id
                        job_execution.save()
                    except Exception:
                        # If revoke/resubmit fails, at least we updated the database record
                        pass

            return True
        except Exception:
            return False
