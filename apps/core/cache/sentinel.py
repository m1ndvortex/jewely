"""
Custom connection factory for Redis Sentinel with django-redis.

This factory properly initializes Sentinel connection pools for high availability.
"""

from typing import Any
from urllib.parse import urlparse
from redis.sentinel import Sentinel
from redis import Redis
from django_redis.pool import ConnectionFactory


class SentinelConnectionFactory(ConnectionFactory):
    """
    Connection factory for Redis Sentinel.

    Creates Redis client instances through Sentinel for high availability.
    Overrides connect() to return Sentinel-managed Redis clients.
    """

    def __init__(self, options: dict[str, Any]):
        super().__init__(options)
        self.sentinel_managers = {}  # Cache sentinel managers by service name

    def connect(self, url: str):
        """
        Create a Redis connection pool through Sentinel.

        This is the main entry point called by django-redis when establishing connections.
        We parse the URL, create/get a Sentinel manager, and return a Sentinel-managed pool.

        Args:
            url: Redis URL in format redis://service-name/db

        Returns:
            Connection pool managed by Sentinel
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"SentinelConnectionFactory.connect() called with url: {url}")

        # Parse the URL to get service name and db
        parsed = urlparse(url)
        service_name = parsed.hostname or "mymaster"
        db = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0

        logger.info(f"Connecting to Sentinel service: {service_name}, db: {db}")

        # Get Sentinel configuration from options
        sentinels = self.options.get("SENTINELS", [])
        sentinel_kwargs = self.options.get("SENTINEL_KWARGS", {})

        logger.info(f"Using Sentinel endpoints: {sentinels}")

        # Create or get cached Sentinel manager for this service
        if service_name not in self.sentinel_managers:
            self.sentinel_managers[service_name] = Sentinel(
                sentinels, sentinel_kwargs=sentinel_kwargs
            )
            logger.info(f"Created new Sentinel manager for {service_name}")

        sentinel = self.sentinel_managers[service_name]

        # Build connection kwargs for Redis master
        connection_kwargs = {"db": db}

        # Add password if provided (for Redis master, not Sentinel)
        password = self.options.get("PASSWORD")
        if password:
            connection_kwargs["password"] = password

        # Add socket timeouts if configured
        socket_timeout = self.options.get("SOCKET_TIMEOUT")
        if socket_timeout:
            connection_kwargs["socket_timeout"] = socket_timeout

        socket_connect_timeout = self.options.get("SOCKET_CONNECT_TIMEOUT")
        if socket_connect_timeout:
            connection_kwargs["socket_connect_timeout"] = socket_connect_timeout

        # Get max_connections from options
        max_connections = self.options.get("MAX_CONNECTIONS", 50)
        connection_kwargs["max_connections"] = max_connections

        # Get Redis client for master through Sentinel
        # master_for() returns a fully configured Redis client with SentinelConnectionPool
        redis_client = sentinel.master_for(service_name, **connection_kwargs)

        logger.info(f"Successfully got Redis client from Sentinel for {service_name}")

        # Return the configured Redis client directly
        # This client has a SentinelConnectionPool that will handle master discovery
        return redis_client
