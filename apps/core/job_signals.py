"""
Celery signal handlers for job performance tracking.

This module provides signal handlers for:
- Tracking job execution start and completion
- Monitoring CPU and memory usage
- Recording performance metrics

Per Requirement 33 - Scheduled Job Management
Requirement 33.9: Track execution times and identify slow jobs.
Requirement 33.10: Track CPU and memory usage per job type.
"""

import logging
import os
import time
from typing import Optional

from django.utils import timezone

from celery import signals
from celery.app.task import Task

from apps.core.job_models import JobExecution

logger = logging.getLogger(__name__)


# Store task start times and resource usage
_task_start_times = {}
_task_start_resources = {}


def get_process_resources() -> Optional[dict]:
    """
    Get current process CPU and memory usage.

    Returns:
        dict with cpu_percent and memory_mb, or None if psutil not available
    """
    try:
        import psutil

        process = psutil.Process(os.getpid())

        # Get CPU percent (non-blocking)
        cpu_percent = process.cpu_percent(interval=None)

        # Get memory info
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert bytes to MB

        return {"cpu_percent": cpu_percent, "memory_mb": memory_mb}
    except ImportError:
        # psutil not installed
        return None
    except Exception as e:
        logger.warning(f"Failed to get process resources: {e}")
        return None


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """
    Handle task prerun signal - record start time and initial resources.

    Requirement 33.9: Track execution times.
    Requirement 33.10: Track CPU and memory usage per job type.
    """
    try:
        # Record start time
        _task_start_times[task_id] = time.time()

        # Record initial resources
        resources = get_process_resources()
        if resources:
            _task_start_resources[task_id] = resources

        # Create or update JobExecution record
        task_name = task.name if isinstance(task, Task) else str(sender)

        JobExecution.objects.update_or_create(
            task_id=task_id,
            defaults={
                "task_name": task_name,
                "status": "STARTED",
                "args": list(args) if args else [],
                "kwargs": dict(kwargs) if kwargs else {},
                "started_at": timezone.now(),
            },
        )

    except Exception as e:
        logger.error(f"Error in task_prerun_handler for {task_id}: {e}")


@signals.task_postrun.connect
def task_postrun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra
):
    """
    Handle task postrun signal - record completion, execution time, and resource usage.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """
    try:
        # Calculate execution time
        execution_time = None
        if task_id in _task_start_times:
            execution_time = time.time() - _task_start_times[task_id]
            del _task_start_times[task_id]

        # Get final resources and calculate usage
        cpu_percent = None
        memory_mb = None
        peak_memory_mb = None

        final_resources = get_process_resources()
        if final_resources and task_id in _task_start_resources:
            start_resources = _task_start_resources[task_id]

            # Calculate average CPU (simple average of start and end)
            cpu_percent = (start_resources["cpu_percent"] + final_resources["cpu_percent"]) / 2

            # Use final memory as the measurement
            memory_mb = final_resources["memory_mb"]

            # Peak memory is the higher of start or end
            peak_memory_mb = max(start_resources["memory_mb"], final_resources["memory_mb"])

            del _task_start_resources[task_id]

        # Update JobExecution record
        task_name = task.name if isinstance(task, Task) else str(sender)

        try:
            job = JobExecution.objects.get(task_id=task_id)
            job.status = "SUCCESS" if state == "SUCCESS" else state or "SUCCESS"
            job.completed_at = timezone.now()
            job.execution_time = execution_time
            job.result = str(retval) if retval else None
            job.cpu_percent = cpu_percent
            job.memory_mb = memory_mb
            job.peak_memory_mb = peak_memory_mb
            job.save()

        except JobExecution.DoesNotExist:
            # Create new record if it doesn't exist
            JobExecution.objects.create(
                task_id=task_id,
                task_name=task_name,
                status="SUCCESS" if state == "SUCCESS" else state or "SUCCESS",
                args=list(args) if args else [],
                kwargs=dict(kwargs) if kwargs else {},
                completed_at=timezone.now(),
                execution_time=execution_time,
                result=str(retval) if retval else None,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                peak_memory_mb=peak_memory_mb,
            )

        # Update statistics for this task type
        from apps.core.job_service import JobMonitoringService

        JobMonitoringService.update_job_statistics(task_name)

    except Exception as e:
        logger.error(f"Error in task_postrun_handler for {task_id}: {e}")


@signals.task_failure.connect
def task_failure_handler(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **extra,
):
    """
    Handle task failure signal - record error details.

    Requirement 33.4: Display failed jobs with error details and retry options.
    """
    try:
        # Calculate execution time if available
        execution_time = None
        if task_id in _task_start_times:
            execution_time = time.time() - _task_start_times[task_id]
            del _task_start_times[task_id]

        # Get resource usage if available
        cpu_percent = None
        memory_mb = None
        peak_memory_mb = None

        final_resources = get_process_resources()
        if final_resources and task_id in _task_start_resources:
            start_resources = _task_start_resources[task_id]
            cpu_percent = (start_resources["cpu_percent"] + final_resources["cpu_percent"]) / 2
            memory_mb = final_resources["memory_mb"]
            peak_memory_mb = max(start_resources["memory_mb"], final_resources["memory_mb"])
            del _task_start_resources[task_id]

        # Update JobExecution record
        task_name = sender.name if hasattr(sender, "name") else str(sender)

        try:
            job = JobExecution.objects.get(task_id=task_id)
            job.status = "FAILURE"
            job.completed_at = timezone.now()
            job.execution_time = execution_time
            job.error = str(exception) if exception else "Unknown error"
            job.traceback = str(traceback) if traceback else (str(einfo) if einfo else None)
            job.cpu_percent = cpu_percent
            job.memory_mb = memory_mb
            job.peak_memory_mb = peak_memory_mb
            job.save()

        except JobExecution.DoesNotExist:
            # Create new record if it doesn't exist
            JobExecution.objects.create(
                task_id=task_id,
                task_name=task_name,
                status="FAILURE",
                args=list(args) if args else [],
                kwargs=dict(kwargs) if kwargs else {},
                completed_at=timezone.now(),
                execution_time=execution_time,
                error=str(exception) if exception else "Unknown error",
                traceback=str(traceback) if traceback else (str(einfo) if einfo else None),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                peak_memory_mb=peak_memory_mb,
            )

        # Update statistics for this task type
        from apps.core.job_service import JobMonitoringService

        JobMonitoringService.update_job_statistics(task_name)

    except Exception as e:
        logger.error(f"Error in task_failure_handler for {task_id}: {e}")


@signals.task_revoked.connect
def task_revoked_handler(
    sender=None, request=None, terminated=None, signum=None, expired=None, **extra
):
    """
    Handle task revoked signal - mark task as revoked.

    Requirement 33.8: Allow administrators to cancel running or pending jobs.
    """
    try:
        task_id = request.id if request else None
        if not task_id:
            return

        # Clean up tracking data
        if task_id in _task_start_times:
            del _task_start_times[task_id]
        if task_id in _task_start_resources:
            del _task_start_resources[task_id]

        # Update JobExecution record
        try:
            job = JobExecution.objects.get(task_id=task_id)
            job.status = "REVOKED"
            job.completed_at = timezone.now()
            job.save()
        except JobExecution.DoesNotExist:
            pass

    except Exception as e:
        logger.error(f"Error in task_revoked_handler for {task_id}: {e}")
