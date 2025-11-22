"""
Custom Django Redis client for Sentinel support.

This client properly initializes connections through Redis Sentinel.
"""

from typing import Any
from redis import Redis
from django_redis.client.default import DefaultClient
from apps.core.cache.sentinel import SentinelConnectionFactory


class SentinelAwareClient(DefaultClient):
    """
    Custom Redis client that uses Sentinel connection factory.

    This client extends DefaultClient to support Redis Sentinel
    by using our custom connection factory.
    """

    def __init__(self, server, params, backend):
        """Initialize client with Sentinel-aware connection factory."""
        super().__init__(server, params, backend)

        # Force use of our Sentinel connection factory
        if params.get("OPTIONS", {}).get("SENTINELS"):
            self.connection_factory = SentinelConnectionFactory(params["OPTIONS"])

    def connect(self, index=0):
        """
        Override connect to return a Sentinel-managed Redis client.

        This is called by the parent get_client() method to create connections.
        The parent handles caching via self._clients.

        Returns:
            Redis client instance configured by Sentinel with SentinelConnectionPool
        """
        # Get Redis client from our Sentinel factory
        # This returns a fully configured client with SentinelConnectionPool
        return self.connection_factory.connect(self._server[index])
