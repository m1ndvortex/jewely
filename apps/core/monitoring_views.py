"""
Monitoring dashboard views for platform administrators.

This module provides comprehensive monitoring dashboards for:
- System overview (CPU, memory, disk, network)
- Service status indicators
- Database monitoring
- Cache monitoring
- Celery monitoring

Per Requirements 7 and 24 - System Monitoring and Observability
"""

import platform

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

import psutil
import redis
from celery.app.control import Inspect

from apps.core.admin_views import PlatformAdminRequiredMixin


class MonitoringDashboardView(PlatformAdminRequiredMixin, TemplateView):
    """
    Main monitoring dashboard view.

    Requirement 7.1: Display real-time metrics for CPU usage, memory usage,
    disk space, and database connections.

    Requirement 7.2: Monitor status of all critical services including Django,
    PostgreSQL, Redis, Celery, and Nginx.
    """

    template_name = "monitoring/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get system overview
        context["system_info"] = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        }

        # Get service status
        context["services"] = self._get_service_status()

        return context

    def _get_service_status(self):
        """Get status of all critical services."""
        services = {
            "django": {"name": "Django", "status": "up", "message": "Running"},
            "postgresql": self._check_postgresql(),
            "redis": self._check_redis(),
            "celery": self._check_celery(),
            "nginx": {"name": "Nginx", "status": "unknown", "message": "Check via Prometheus"},
        }
        return services

    def _check_postgresql(self):
        """Check PostgreSQL database status."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                return {
                    "name": "PostgreSQL",
                    "status": "up",
                    "message": "Connected",
                    "version": version.split(",")[0],
                }
        except Exception as e:
            return {"name": "PostgreSQL", "status": "down", "message": str(e)}

    def _check_redis(self):
        """Check Redis cache status."""
        try:
            cache.set("health_check", "ok", 10)
            result = cache.get("health_check")
            if result == "ok":
                # Get Redis info
                redis_client = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
                info = redis_client.info()
                return {
                    "name": "Redis",
                    "status": "up",
                    "message": "Connected",
                    "version": info.get("redis_version", "Unknown"),
                }
            else:
                return {
                    "name": "Redis",
                    "status": "degraded",
                    "message": "Cache not working properly",
                }
        except Exception as e:
            return {"name": "Redis", "status": "down", "message": str(e)}

    def _check_celery(self):
        """Check Celery worker status."""
        try:
            from config.celery import app

            inspect = Inspect(app=app)
            stats = inspect.stats()

            if stats:
                worker_count = len(stats)
                return {
                    "name": "Celery",
                    "status": "up",
                    "message": f"{worker_count} worker(s) active",
                    "workers": worker_count,
                }
            else:
                return {"name": "Celery", "status": "down", "message": "No workers found"}
        except Exception as e:
            return {"name": "Celery", "status": "down", "message": str(e)}


class SystemMetricsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for real-time system metrics.

    Requirement 7.1: Display real-time metrics for CPU usage, memory usage,
    disk space, and database connections.
    """

    def get(self, request):
        """Get current system metrics."""
        metrics = {
            "cpu": self._get_cpu_metrics(),
            "memory": self._get_memory_metrics(),
            "disk": self._get_disk_metrics(),
            "network": self._get_network_metrics(),
            "timestamp": timezone.now().isoformat(),
        }

        return JsonResponse(metrics)

    def _get_cpu_metrics(self):
        """Get CPU usage metrics."""
        cpu_percent = psutil.cpu_percent(interval=1, percpu=False)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        return {
            "usage_percent": round(cpu_percent, 2),
            "count": cpu_count,
            "frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
            "status": "critical" if cpu_percent > 90 else "warning" if cpu_percent > 80 else "ok",
        }

    def _get_memory_metrics(self):
        """Get memory usage metrics."""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "usage_percent": round(memory.percent, 2),
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": round(swap.percent, 2),
            "status": (
                "critical" if memory.percent > 90 else "warning" if memory.percent > 80 else "ok"
            ),
        }

    def _get_disk_metrics(self):
        """Get disk usage metrics."""
        disk = psutil.disk_usage("/")

        return {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "usage_percent": round(disk.percent, 2),
            "status": "critical" if disk.percent > 90 else "warning" if disk.percent > 80 else "ok",
        }

    def _get_network_metrics(self):
        """Get network I/O metrics."""
        net_io = psutil.net_io_counters()

        return {
            "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errors_in": net_io.errin,
            "errors_out": net_io.errout,
            "drops_in": net_io.dropin,
            "drops_out": net_io.dropout,
        }


class DatabaseMetricsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for database monitoring metrics.

    Requirement 7.2: Monitor database connections, query performance.
    """

    def get(self, request):
        """Get current database metrics."""
        metrics = {
            "connections": self._get_connection_metrics(),
            "activity": self._get_activity_metrics(),
            "performance": self._get_performance_metrics(),
            "size": self._get_database_size(),
            "timestamp": timezone.now().isoformat(),
        }

        return JsonResponse(metrics)

    def _get_connection_metrics(self):
        """Get database connection metrics."""
        try:
            with connection.cursor() as cursor:
                # Get connection count
                cursor.execute(
                    """
                    SELECT count(*) as total,
                           count(*) FILTER (WHERE state = 'active') as active,
                           count(*) FILTER (WHERE state = 'idle') as idle,
                           count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """
                )
                row = cursor.fetchone()

                # Get max connections
                cursor.execute("SHOW max_connections")
                max_conn = int(cursor.fetchone()[0])

                total, active, idle, idle_in_trans = row
                usage_percent = round((total / max_conn) * 100, 2) if max_conn > 0 else 0

                return {
                    "total": total,
                    "active": active,
                    "idle": idle,
                    "idle_in_transaction": idle_in_trans,
                    "max_connections": max_conn,
                    "usage_percent": usage_percent,
                    "status": (
                        "critical"
                        if usage_percent > 90
                        else "warning" if usage_percent > 80 else "ok"
                    ),
                }
        except Exception as e:
            return {"error": str(e)}

    def _get_activity_metrics(self):
        """Get database activity metrics."""
        try:
            with connection.cursor() as cursor:
                # Get transaction stats
                cursor.execute(
                    """
                    SELECT
                        xact_commit,
                        xact_rollback,
                        blks_read,
                        blks_hit,
                        tup_returned,
                        tup_fetched,
                        tup_inserted,
                        tup_updated,
                        tup_deleted
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """
                )
                row = cursor.fetchone()

                if row:
                    (
                        commits,
                        rollbacks,
                        blks_read,
                        blks_hit,
                        tup_ret,
                        tup_fetch,
                        tup_ins,
                        tup_upd,
                        tup_del,
                    ) = row

                    # Calculate cache hit ratio
                    total_blocks = blks_read + blks_hit
                    cache_hit_ratio = (
                        round((blks_hit / total_blocks * 100), 2) if total_blocks > 0 else 0
                    )

                    return {
                        "commits": commits,
                        "rollbacks": rollbacks,
                        "cache_hit_ratio": cache_hit_ratio,
                        "tuples_returned": tup_ret,
                        "tuples_fetched": tup_fetch,
                        "tuples_inserted": tup_ins,
                        "tuples_updated": tup_upd,
                        "tuples_deleted": tup_del,
                    }
                return {}
        except Exception as e:
            return {"error": str(e)}

    def _get_performance_metrics(self):
        """Get slow queries and performance metrics."""
        try:
            with connection.cursor() as cursor:
                # Get long-running queries
                cursor.execute(
                    """
                    SELECT count(*) as slow_queries
                    FROM pg_stat_activity
                    WHERE state = 'active'
                    AND query_start < now() - interval '5 seconds'
                    AND query NOT LIKE '%pg_stat_activity%'
                """
                )
                slow_queries = cursor.fetchone()[0]

                # Get table sizes
                cursor.execute(
                    """
                    SELECT count(*) as table_count
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """
                )
                table_count = cursor.fetchone()[0]

                return {
                    "slow_queries": slow_queries,
                    "table_count": table_count,
                }
        except Exception as e:
            return {"error": str(e)}

    def _get_database_size(self):
        """Get database size information."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database())")
                size_bytes = cursor.fetchone()[0]
                size_mb = round(size_bytes / (1024**2), 2)
                size_gb = round(size_bytes / (1024**3), 2)

                return {
                    "size_mb": size_mb,
                    "size_gb": size_gb,
                }
        except Exception as e:
            return {"error": str(e)}


class CacheMetricsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for Redis cache monitoring metrics.

    Requirement 7.4: Monitor cache hit rates.
    """

    def get(self, request):
        """Get current cache metrics."""
        metrics = {
            "redis": self._get_redis_metrics(),
            "timestamp": timezone.now().isoformat(),
        }

        return JsonResponse(metrics)

    def _get_redis_metrics(self):
        """Get Redis cache metrics."""
        try:
            redis_client = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
            info = redis_client.info()

            # Calculate hit rate
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total_requests = hits + misses
            hit_rate = round((hits / total_requests * 100), 2) if total_requests > 0 else 0

            # Memory usage
            used_memory = info.get("used_memory", 0)
            used_memory_mb = round(used_memory / (1024**2), 2)
            max_memory = info.get("maxmemory", 0)
            max_memory_mb = round(max_memory / (1024**2), 2) if max_memory > 0 else 0

            memory_percent = round((used_memory / max_memory * 100), 2) if max_memory > 0 else 0

            # Get key count
            db_info = info.get("db0", {})
            if isinstance(db_info, dict):
                key_count = db_info.get("keys", 0)
            else:
                # Parse string format: "keys=X,expires=Y"
                key_count = 0
                if "keys=" in str(db_info):
                    key_count = int(str(db_info).split("keys=")[1].split(",")[0])

            return {
                "version": info.get("redis_version", "Unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": used_memory_mb,
                "max_memory_mb": max_memory_mb,
                "memory_usage_percent": memory_percent,
                "keyspace_hits": hits,
                "keyspace_misses": misses,
                "hit_rate_percent": hit_rate,
                "total_keys": key_count,
                "evicted_keys": info.get("evicted_keys", 0),
                "expired_keys": info.get("expired_keys", 0),
                "ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
                "status": (
                    "critical"
                    if memory_percent > 90
                    else "warning" if memory_percent > 80 else "ok"
                ),
            }
        except Exception as e:
            return {"error": str(e)}


class CeleryMetricsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for Celery monitoring metrics.

    Requirement 7.2: Monitor Celery worker status and queue lengths.
    """

    def get(self, request):
        """Get current Celery metrics."""
        metrics = {
            "workers": self._get_worker_metrics(),
            "queues": self._get_queue_metrics(),
            "tasks": self._get_task_metrics(),
            "timestamp": timezone.now().isoformat(),
        }

        return JsonResponse(metrics)

    def _get_worker_metrics(self):
        """Get Celery worker metrics."""
        try:
            from config.celery import app

            inspect = Inspect(app=app)

            # Get worker stats
            stats = inspect.stats()
            active_tasks = inspect.active()
            registered_tasks = inspect.registered()

            workers = []
            if stats:
                for worker_name, worker_stats in stats.items():
                    workers.append(
                        {
                            "name": worker_name,
                            "status": "online",
                            "pool": worker_stats.get("pool", {}).get("implementation", "Unknown"),
                            "max_concurrency": worker_stats.get("pool", {}).get(
                                "max-concurrency", 0
                            ),
                            "active_tasks": (
                                len(active_tasks.get(worker_name, [])) if active_tasks else 0
                            ),
                            "registered_tasks": (
                                len(registered_tasks.get(worker_name, []))
                                if registered_tasks
                                else 0
                            ),
                        }
                    )

            return {
                "total_workers": len(workers),
                "workers": workers,
                "status": "ok" if len(workers) > 0 else "critical",
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _get_queue_metrics(self):
        """Get Celery queue metrics."""
        try:
            from config.celery import app

            inspect = Inspect(app=app)

            # Get reserved tasks (tasks in queue)
            reserved = inspect.reserved()
            scheduled = inspect.scheduled()

            total_reserved = 0
            total_scheduled = 0

            if reserved:
                for tasks in reserved.values():
                    total_reserved += len(tasks)

            if scheduled:
                for tasks in scheduled.values():
                    total_scheduled += len(tasks)

            return {
                "reserved_tasks": total_reserved,
                "scheduled_tasks": total_scheduled,
                "total_pending": total_reserved + total_scheduled,
                "status": "warning" if (total_reserved + total_scheduled) > 100 else "ok",
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_task_metrics(self):
        """Get Celery task execution metrics."""
        try:
            # This would typically come from Celery events or a monitoring backend
            # For now, return basic info
            return {"note": "Task metrics available via Prometheus or Flower"}
        except Exception as e:
            return {"error": str(e)}


class ServiceStatusAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for service status checks.

    Requirement 7.2: Monitor status of all critical services.
    """

    def get(self, request):
        """Get status of all services."""
        services = {
            "django": self._check_django(),
            "postgresql": self._check_postgresql(),
            "redis": self._check_redis(),
            "celery": self._check_celery(),
            "timestamp": timezone.now().isoformat(),
        }

        return JsonResponse(services)

    def _check_django(self):
        """Check Django application status."""
        return {
            "name": "Django",
            "status": "up",
            "message": "Application running",
            "version": settings.VERSION if hasattr(settings, "VERSION") else "Unknown",
        }

    def _check_postgresql(self):
        """Check PostgreSQL status."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version(), pg_is_in_recovery()")
                version, is_replica = cursor.fetchone()

                return {
                    "name": "PostgreSQL",
                    "status": "up",
                    "message": "Connected",
                    "version": version.split(",")[0],
                    "is_replica": is_replica,
                }
        except Exception as e:
            return {"name": "PostgreSQL", "status": "down", "message": str(e)}

    def _check_redis(self):
        """Check Redis status."""
        try:
            redis_client = redis.Redis.from_url(settings.CACHES["default"]["LOCATION"])
            info = redis_client.info()

            return {
                "name": "Redis",
                "status": "up",
                "message": "Connected",
                "version": info.get("redis_version", "Unknown"),
                "role": info.get("role", "Unknown"),
            }
        except Exception as e:
            return {"name": "Redis", "status": "down", "message": str(e)}

    def _check_celery(self):
        """Check Celery status."""
        try:
            from config.celery import app

            inspect = Inspect(app=app)
            stats = inspect.stats()

            if stats:
                return {
                    "name": "Celery",
                    "status": "up",
                    "message": f"{len(stats)} worker(s) active",
                    "workers": len(stats),
                }
            else:
                return {"name": "Celery", "status": "down", "message": "No workers found"}
        except Exception as e:
            return {"name": "Celery", "status": "down", "message": str(e)}
