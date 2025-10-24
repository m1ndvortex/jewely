"""
Signal handlers for the reporting app.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.reporting.models import ReportExecution, ReportSchedule

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ReportSchedule)
def update_schedule_next_run(sender, instance, created, **kwargs):
    """
    Update next_run_at when a schedule is created or modified.
    """
    if created or instance.status == "ACTIVE":
        # Calculate and update next run time
        instance.update_next_run()
        logger.info(f"Updated next run time for schedule: {instance.name}")


@receiver(post_save, sender=ReportExecution)
def log_execution_completion(sender, instance, created, **kwargs):
    """
    Log when a report execution is completed or failed.
    """
    if not created and instance.status in ["COMPLETED", "FAILED"]:
        if instance.status == "COMPLETED":
            logger.info(
                f"Report execution completed: {instance.report.name} "
                f"({instance.row_count} rows, {instance.duration_display})"
            )
        else:
            logger.error(
                f"Report execution failed: {instance.report.name} " f"- {instance.error_message}"
            )


@receiver(post_delete, sender=ReportExecution)
def cleanup_execution_files(sender, instance, **kwargs):
    """
    Clean up report files when execution records are deleted.
    """
    if instance.result_file_path:
        try:
            import os

            if os.path.exists(instance.result_file_path):
                os.remove(instance.result_file_path)
                logger.info(f"Cleaned up report file: {instance.result_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up report file {instance.result_file_path}: {e}")
