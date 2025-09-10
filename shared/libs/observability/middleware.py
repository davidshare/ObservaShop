"""
FastAPI middleware for Prometheus metrics collection.
Separated for clarity and reusability.
"""

import re
import time
from typing import Awaitable, Callable

from fastapi import Request, Response

from shared.libs.observability.metrics import (
    ACTIVE_REQUESTS,
    REQUEST_COUNT,
    REQUEST_DURATION,
    EXCEPTION_COUNT,
)


async def metrics_middleware(
    request: Request, call_next: Callable[..., Awaitable[Response]]
) -> Response:
    """
    Middleware to collect HTTP request metrics.

    Tracks:
    - Request count
    - Request duration
    - Active requests
    - Exceptions (by type)
    """
    method = request.method

    # Clean endpoint (replace UUIDs with {id})
    path = request.url.path
    if re.search(r"/[a-f0-9-]{36}", path):
        path = re.sub(r"/[a-f0-9-]{36}", "/{id}", path)

    ACTIVE_REQUESTS.labels(method=method, endpoint=path).inc()
    start_time = time.time()
    exception_type = None

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        # Capture the exception type
        exception_type = type(e).__name__
        EXCEPTION_COUNT.labels(
            exception_type=exception_type, method=method, endpoint=path
        ).inc()
        status_code = 500
        raise
    finally:
        duration = time.time() - start_time
        ACTIVE_REQUESTS.labels(method=method, endpoint=path).dec()

        # Always record request metrics
        REQUEST_COUNT.labels(
            method=method, endpoint=path, status=str(status_code)
        ).inc()

        REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)

    return response
