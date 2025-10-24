"""
Celery tasks for report scheduling and execution.

Implements Requirement 15: Advanced Reporting and Analytics
- Scheduled report execution
- Report delivery via email
- Report cleanup tasks
"""

import logging
import os
from datetime import timedelta
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from celery import shared_task

from apps.core.models import Tenant
from apps.reporting.models import Report, ReportExecution, ReportSchedule
from apps.reporting.services import ReportExecutionService

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name="apps.reporting.tasks.execute_scheduled_reports",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def execute_scheduled_reports(self) -> str:
    """
    Execute all scheduled reports that are due.

    This task runs every 15 minutes to check for scheduled reports.

    Returns:
        str: Summary of executed reports
    """
    try:
        logger.info("Checking for scheduled reports to execute")

        # Get all active schedules that are due
        now = timezone.now()
        due_schedules = ReportSchedule.objects.filter(
            status="ACTIVE", next_run_at__lte=now
        ).select_related("report", "report__tenant", "created_by")

        executed_count = 0
        failed_count = 0

        for schedule in due_schedules:
            try:
                # Execute the scheduled report
                execute_scheduled_report.delay(schedule.id)
                executed_count += 1

                logger.info(f"Queued scheduled report: {schedule.name}")

            except Exception as e:
                logger.error(f"Failed to queue scheduled report {schedule.name}: {e}")
                failed_count += 1

        summary = f"Queued {executed_count} scheduled reports, {failed_count} failed"
        logger.info(summary)

        return summary

    except Exception as e:
        logger.exception(f"Error checking scheduled reports: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="apps.reporting.tasks.execute_scheduled_report",
    bind=True,
    max_retries=2,
    default_retry_delay=600,  # 10 minutes
)
def execute_scheduled_report(self, schedule_id: str) -> Optional[str]:
    """
    Execute a specific scheduled report.

    Args:
        schedule_id: UUID of the ReportSchedule

    Returns:
        str: Execution summary or None on failure
    """
    try:
        # Get the schedule
        schedule = ReportSchedule.objects.select_related(
            "report", "report__tenant", "created_by"
        ).get(id=schedule_id)

        logger.info(f"Executing scheduled report: {schedule.name}")

        # Check if schedule is still active
        if schedule.status != "ACTIVE":
            logger.warning(f"Schedule {schedule.name} is no longer active, skipping")
            return None

        # Check if we're past the end date
        if schedule.end_date and timezone.now() > schedule.end_date:
            logger.info(f"Schedule {schedule.name} has ended, marking as completed")
            schedule.status = "COMPLETED"
            schedule.save(update_fields=["status"])
            return None

        # Execute the report
        execution_service = ReportExecutionService(schedule.report.tenant)

        execution = execution_service.execute_report(
            report=schedule.report,
            parameters=schedule.parameters,
            output_format=schedule.output_format,
            user=schedule.created_by,
            email_recipients=schedule.email_recipients,
            trigger_type="SCHEDULED",
        )

        # Link execution to schedule
        execution.schedule = schedule
        execution.save(update_fields=["schedule"])

        # Update schedule statistics
        schedule.last_run_at = timezone.now()
        schedule.run_count += 1
        schedule.update_next_run()
        schedule.save(update_fields=["last_run_at", "run_count", "next_run_at"])

        logger.info(f"Successfully executed scheduled report: {schedule.name}")

        return f"Executed report {schedule.report.name}: {execution.row_count} rows"

    except ReportSchedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found")
        return None

    except Exception as e:
        logger.error(f"Failed to execute scheduled report {schedule_id}: {e}")

        # Mark schedule as failed if max retries exceeded
        if self.request.retries >= self.max_retries:
            try:
                schedule = ReportSchedule.objects.get(id=schedule_id)
                schedule.status = "FAILED"
                schedule.save(update_fields=["status"])
                logger.error(f"Marked schedule {schedule.name} as failed after max retries")
            except ReportSchedule.DoesNotExist:
                pass

        raise self.retry(exc=e)


@shared_task(
    name="apps.reporting.tasks.execute_report_async",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def execute_report_async(
    self,
    tenant_id: str,
    report_id: str,
    parameters: Dict,
    output_format: str,
    user_id: int,
    email_recipients: List[str] = None,
) -> Optional[str]:
    """
    Execute a report asynchronously.

    This task is used for manual report execution that might take a long time.

    Args:
        tenant_id: Tenant UUID
        report_id: Report UUID
        parameters: Report parameters
        output_format: Output format
        user_id: User ID who requested the report
        email_recipients: Optional email recipients

    Returns:
        str: Execution summary or None on failure
    """
    try:
        # Get required objects
        tenant = Tenant.objects.get(id=tenant_id)
        report = Report.objects.get(id=report_id, tenant=tenant)
        user = User.objects.get(id=user_id)

        logger.info(f"Executing async report: {report.name} for tenant {tenant.company_name}")

        # Execute the report
        execution_service = ReportExecutionService(tenant)

        execution = execution_service.execute_report(
            report=report,
            parameters=parameters,
            output_format=output_format,
            user=user,
            email_recipients=email_recipients,
            trigger_type="MANUAL",
        )

        # Store the Celery task ID
        execution.celery_task_id = self.request.id
        execution.save(update_fields=["celery_task_id"])

        logger.info(f"Successfully executed async report: {report.name}")

        return f"Executed report {report.name}: {execution.row_count} rows"

    except (Tenant.DoesNotExist, Report.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Object not found for async report execution: {e}")
        return None

    except Exception as e:
        logger.error(f"Failed to execute async report: {e}")
        raise self.retry(exc=e)


@shared_task(name="apps.reporting.tasks.cleanup_old_report_files")
def cleanup_old_report_files(days_to_keep: int = 30) -> str:
    """
    Clean up old report files to free disk space.

    Args:
        days_to_keep: Number of days to keep report files

    Returns:
        str: Cleanup summary
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Get old executions with files
        old_executions = ReportExecution.objects.filter(
            completed_at__lt=cutoff_date, result_file_path__isnull=False
        ).exclude(result_file_path="")

        deleted_files = 0
        freed_bytes = 0

        for execution in old_executions:
            try:
                if os.path.exists(execution.result_file_path):
                    file_size = os.path.getsize(execution.result_file_path)
                    os.remove(execution.result_file_path)
                    deleted_files += 1
                    freed_bytes += file_size

                    # Clear the file path
                    execution.result_file_path = ""
                    execution.save(update_fields=["result_file_path"])

            except Exception as e:
                logger.warning(f"Failed to delete report file {execution.result_file_path}: {e}")

        # Convert bytes to MB
        freed_mb = freed_bytes / (1024 * 1024)

        summary = f"Deleted {deleted_files} old report files, freed {freed_mb:.2f} MB"
        logger.info(summary)

        return summary

    except Exception as e:
        logger.exception(f"Error cleaning up old report files: {e}")
        raise


@shared_task(name="apps.reporting.tasks.cleanup_old_executions")
def cleanup_old_executions(days_to_keep: int = 90) -> str:
    """
    Clean up old report execution records.

    Args:
        days_to_keep: Number of days to keep execution records

    Returns:
        str: Cleanup summary
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Delete old execution records (keep successful ones longer)
        failed_executions = ReportExecution.objects.filter(
            completed_at__lt=cutoff_date, status="FAILED"
        )

        old_executions = ReportExecution.objects.filter(
            completed_at__lt=cutoff_date
            - timedelta(days=30),  # Keep successful ones 30 days longer
            status="COMPLETED",
        )

        failed_count = failed_executions.count()
        old_count = old_executions.count()

        failed_executions.delete()
        old_executions.delete()

        total_deleted = failed_count + old_count

        summary = f"Deleted {total_deleted} old execution records ({failed_count} failed, {old_count} old)"
        logger.info(summary)

        return summary

    except Exception as e:
        logger.exception(f"Error cleaning up old executions: {e}")
        raise


@shared_task(name="apps.reporting.tasks.update_schedule_next_runs")
def update_schedule_next_runs() -> str:
    """
    Update next_run_at for all active schedules.

    This task runs daily to ensure schedules have correct next run times.

    Returns:
        str: Update summary
    """
    try:
        active_schedules = ReportSchedule.objects.filter(status="ACTIVE")
        updated_count = 0

        for schedule in active_schedules:
            old_next_run = schedule.next_run_at
            schedule.update_next_run()

            if schedule.next_run_at != old_next_run:
                updated_count += 1

        summary = f"Updated next run times for {updated_count} schedules"
        logger.info(summary)

        return summary

    except Exception as e:
        logger.exception(f"Error updating schedule next runs: {e}")
        raise


@shared_task(name="apps.reporting.tasks.generate_report_usage_stats")
def generate_report_usage_stats() -> str:
    """
    Generate usage statistics for reports.

    This task runs weekly to track report usage patterns.

    Returns:
        str: Statistics summary
    """
    try:
        from django.db import models

        # Get stats for the last 7 days
        week_ago = timezone.now() - timedelta(days=7)

        # Most popular reports
        popular_reports = (
            ReportExecution.objects.filter(started_at__gte=week_ago, status="COMPLETED")
            .values("report__name", "report__tenant__company_name")
            .annotate(execution_count=models.Count("id"))
            .order_by("-execution_count")[:10]
        )

        # Tenant usage
        tenant_usage = (
            ReportExecution.objects.filter(started_at__gte=week_ago, status="COMPLETED")
            .values("report__tenant__company_name")
            .annotate(execution_count=models.Count("id"), total_rows=models.Sum("row_count"))
            .order_by("-execution_count")[:10]
        )

        # Log statistics
        logger.info("Weekly Report Usage Statistics:")
        logger.info(f"Popular reports: {list(popular_reports)}")
        logger.info(f"Tenant usage: {list(tenant_usage)}")

        total_executions = ReportExecution.objects.filter(
            started_at__gte=week_ago, status="COMPLETED"
        ).count()

        return f"Generated usage stats: {total_executions} executions in the last week"

    except Exception as e:
        logger.exception(f"Error generating report usage stats: {e}")
        raise
