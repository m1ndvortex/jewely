"""
OpenTelemetry Distributed Tracing Configuration

This module configures OpenTelemetry for distributed tracing across the Django application.
It instruments Django, PostgreSQL, Redis, Celery, and HTTP requests automatically.

Requirements: Requirement 24 - Monitoring and Observability
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def configure_tracing():
    """
    Configure OpenTelemetry distributed tracing for the Django application.
    
    This function:
    1. Creates a TracerProvider with service identification
    2. Configures OTLP exporter to send traces to OpenTelemetry Collector
    3. Instruments Django, PostgreSQL, Redis, Celery, and HTTP requests
    4. Sets up batch span processing for efficient trace export
    
    Environment Variables:
        OTEL_ENABLED: Enable/disable tracing (default: True in production)
        OTEL_SERVICE_NAME: Service name for traces (default: jewelry-shop-django)
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://otel-collector:4317)
        OTEL_EXPORTER_OTLP_INSECURE: Use insecure connection (default: True)
    """
    # Check if tracing is enabled
    otel_enabled = os.getenv("OTEL_ENABLED", "true").lower() == "true"
    if not otel_enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return

    try:
        # Service identification
        service_name = os.getenv("OTEL_SERVICE_NAME", "jewelry-shop-django")
        
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name,
            "deployment.environment": os.getenv("ENVIRONMENT", "production"),
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "service.namespace": "jewelry-shop",
        })

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://otel-collector:4317"
        )
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
        )
        
        # Add batch span processor for efficient export
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Instrument Django
        DjangoInstrumentor().instrument()
        logger.info("Django instrumented for tracing")
        
        # Instrument PostgreSQL
        Psycopg2Instrumentor().instrument()
        logger.info("PostgreSQL instrumented for tracing")
        
        # Instrument Redis
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented for tracing")
        
        # Instrument HTTP requests
        RequestsInstrumentor().instrument()
        logger.info("HTTP requests instrumented for tracing")
        
        # Instrument Celery
        CeleryInstrumentor().instrument()
        logger.info("Celery instrumented for tracing")
        
        logger.info(
            f"OpenTelemetry tracing configured successfully. "
            f"Service: {service_name}, Endpoint: {otlp_endpoint}"
        )
        
    except Exception as e:
        logger.error(f"Failed to configure OpenTelemetry tracing: {e}", exc_info=True)
        # Don't raise - tracing failures shouldn't break the application


def get_tracer(name: str = __name__):
    """
    Get a tracer instance for manual span creation.
    
    Args:
        name: Name of the tracer (typically __name__ of the module)
        
    Returns:
        Tracer instance
        
    Example:
        from apps.core.tracing import get_tracer
        
        tracer = get_tracer(__name__)
        
        with tracer.start_as_current_span("my_operation"):
            # Your code here
            pass
    """
    return trace.get_tracer(name)
