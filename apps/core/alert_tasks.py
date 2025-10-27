"""
Celery tasks for monitoring alerts.

This module provides periodic tasks for:
- Checking system metrics against alert rules
- Escalating unacknowledged alerts
- Auto-resolving alerts

Per Requirements 7 - System Monitoring and Health Dashboard
"""

import logging

from django.conf import settings
from django.db import connection

import psutil
import redis
from celery import shared_task
from celery.app.control import Inspect

from apps.core.alert_models import AlertRule
from apps.core.alert_service import AlertService

logger = logging.getLogger(__name__)


@shared_task(name="check_system_metrics")
def check_system_metrics():  # noqa: C901
    """
    Check system metrics and trigger alerts if thresholds are exceeded.

    Requirement 7.5: Send alerts when system metrics exceed defined thresholds.

    This task should run every 5 minutes.
    """
    logger.info("Checking system metrics for alerts")

    alerts_created = []

    try:
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_alerts = AlertService.check_metric(AlertRule.CPU_USAGE, cpu_percent)
        alerts_created.extend(cpu_alerts)

        # Check memory usage
        memory = psutil.virtual_memory()
        memory_alerts = AlertService.check_metric(AlertRule.MEMORY_USAGE, memory.percent)
        alerts_created.extend(memory_alerts)

        # Check disk usage
        disk = psutil.disk_usage("/")
        disk_alerts = AlertService.check_metric(AlertRule.DISK_USAGE, disk.percent)
        alerts_created.extend(disk_alerts)

        # Check database connections
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) as total
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """
                )
                total_connections = cursor.fetchone()[0]

                cursor.execute("SHOW max_connections")
                max_connections = int(cursor.fetchone()[0])

                connection_percent = (
                    (total_connections / max_connections * 100) if max_connections > 0 else 0
                )

                db_alerts = AlertService.check_metric(
                    AlertRule.DATABASE_CONNECTIONS, connection_percent
                )
                alerts_created.extend(db_alerts)
        except Exception as e:
            logger.error(f"Error checking database connections: {str(e)}")

        # Check Redis memory
        try:
            redis_client = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
            info = redis_client.info()

            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            if max_memory > 0:
                memory_percent = used_memory / max_memory * 100
                redis_alerts = AlertService.check_metric(AlertRule.REDIS_MEMORY, memory_percent)
                alerts_created.extend(redis_alerts)
        except Exception as e:
            logger.error(f"Error checking Redis memory: {str(e)}")

        # Check Celery queue length
        try:
            from config.celery import app

            inspect = Inspect(app=app)
            reserved = inspect.reserved()

            total_reserved = 0
            if reserved:
                for tasks in reserved.values():
                    total_reserved += len(tasks)

            celery_alerts = AlertService.check_metric(AlertRule.CELERY_QUEUE_LENGTH, total_reserved)
            alerts_created.extend(celery_alerts)
        except Exception as e:
            logger.error(f"Error checking Celery queue: {str(e)}")

        logger.info(f"System metrics check complete. Created {len(alerts_created)} alerts.")

    except Exception as e:
        logger.error(f"Error in check_system_metrics task: {str(e)}")

    return len(alerts_created)


@shared_task(name="check_service_health")
def check_service_health():
    """
    Check health of critical services and trigger alerts if down.

    Requirement 7.2: Monitor status of all critical services.

    This task should run every 5 minutes.
    """
    logger.info("Checking service health for alerts")

    alerts_created = []

    try:
        # Check PostgreSQL
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {str(e)}")
            # Trigger service down alert
            service_alerts = AlertService.check_metric(AlertRule.SERVICE_DOWN, 1)
            alerts_created.extend(service_alerts)

        # Check Redis
        try:
            redis_client = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
            redis_client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            service_alerts = AlertService.check_metric(AlertRule.SERVICE_DOWN, 1)
            alerts_created.extend(service_alerts)

        # Check Celery workers
        try:
            from config.celery import app

            inspect = Inspect(app=app)
            stats = inspect.stats()

            if not stats:
                logger.warning("No Celery workers found")
                service_alerts = AlertService.check_metric(AlertRule.SERVICE_DOWN, 1)
                alerts_created.extend(service_alerts)
        except Exception as e:
            logger.error(f"Celery health check failed: {str(e)}")
            service_alerts = AlertService.check_metric(AlertRule.SERVICE_DOWN, 1)
            alerts_created.extend(service_alerts)

        logger.info(f"Service health check complete. Created {len(alerts_created)} alerts.")

    except Exception as e:
        logger.error(f"Error in check_service_health task: {str(e)}")

    return len(alerts_created)


@shared_task(name="check_alert_escalations")
def check_alert_escalations():
    """
    Check for alerts that need escalation.

    Requirement 7.9: Implement alert escalation.

    This task should run every 5 minutes.
    """
    logger.info("Checking for alerts that need escalation")

    try:
        escalated_count = AlertService.check_escalations()
        logger.info(f"Alert escalation check complete. Escalated {escalated_count} alerts.")
        return escalated_count

    except Exception as e:
        logger.error(f"Error in check_alert_escalations task: {str(e)}")
        return 0


@shared_task(name="auto_resolve_alerts")
def auto_resolve_alerts():
    """
    Auto-resolve alerts when metrics return to normal.

    This task should run every 10 minutes.
    """
    logger.info("Checking for alerts that can be auto-resolved")

    try:
        # This would check current metrics and auto-resolve alerts
        # For now, this is a placeholder for future implementation
        logger.info("Auto-resolve check complete.")
        return 0

    except Exception as e:
        logger.error(f"Error in auto_resolve_alerts task: {str(e)}")
        return 0
