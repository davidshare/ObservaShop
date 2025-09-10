"""
Shared Prometheus metrics for ObservaShop.
Used by all microservices.
"""

from fastapi import Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# === UNIVERSAL HTTP METRICS ===
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests by method, endpoint, and status",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    # Custom buckets: 10ms to 10s
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_active_requests", "Current active HTTP requests", ["method", "endpoint"]
)

# === BUSINESS METRICS ===
EVENTS_PROCESSED = Counter(
    "kafka_events_processed_total",
    "Kafka events processed by consumer",
    ["event_type", "status"],
)

CACHE_HITS = Counter("cache_hits_total", "Redis cache hits", ["cache_type"])

CACHE_MISSES = Counter("cache_misses_total", "Redis cache misses", ["cache_type"])

# === SYSTEM METRICS ===
SERVICE_HEALTH = Gauge(
    "service_health", "Service health status (1=healthy, 0=unhealthy)", []
)

DATABASE_CONNECTIONS = Gauge("database_connections", "Current database connections", [])

# === ERROR METRICS ===
EXCEPTION_COUNT = Counter(
    "http_exceptions_total",
    "Total number of exceptions raised by the service",
    ["exception_type", "method", "endpoint"],
)


def create_metrics_endpoint():
    """Create a /metrics endpoint for Prometheus."""

    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return metrics
