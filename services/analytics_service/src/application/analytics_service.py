"""
Analytics service for ObservaShop.
Handles collection, storage, and retrieval of analytics data.
Processes Kafka events and provides insights via API.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlmodel import Float, Numeric, Session, cast, func, select

from src.config.logger_config import log
from src.core.exceptions import (
    CacheError,
    DatabaseError,
    QueryError,
    SchemaValidationError,
    ValidationError,
)
from src.domain.models import Metrics
from src.infrastructure.services import redis_service


class AnalyticsService:
    """
    Main service class for analytics operations.

    Responsibilities:
    - Collects metrics from Kafka events
    - Stores metrics in PostgreSQL
    - Provides cached analytics queries
    - Emits system health events

    Follows Single Responsibility and Dependency Inversion principles.
    """

    def __init__(self, session: Session):
        self.session = session
        # Redis TTL: 5 minutes for analytics cache
        self.cache_ttl = 300

    async def track_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Record an analytics event.

        Args:
            event_type: Type of event (e.g., 'user.login', 'order.created')
            Event payload data

        Raises:
            SchemaValidationError: If input is invalid
            DatabaseError: If database operation fails
            CacheError: If cache operation fails
        """
        try:
            self._validate_event_input(event_type, data)

            metric = Metrics(metric_type=event_type, value=data)
            self.session.add(metric)
            self.session.commit()
            self.session.refresh(metric)

            # Invalidate related cache
            await self._invalidate_event_cache(event_type)

            log.info(
                "Event tracked", event_type=event_type, user_id=data.get("user_id")
            )

        except SchemaValidationError:
            raise
        except ValidationError as e:
            log.warning("Validation failed", error=str(e))
            raise SchemaValidationError(f"Invalid event data: {str(e)}") from e
        except DatabaseError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error tracking event",
                event_type=event_type,
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError(f"Failed to track event: {str(e)}") from e

    async def get_user_activity_summary(
        self, days: int = 7, user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get user activity summary with Redis caching.

        Args:
            days: Number of days to look back (1-90)
            user_id: Optional filter by user

        Returns:
            Summary of user activity

        Raises:
            SchemaValidationError: If input parameters are invalid
            QueryError: If database query fails
            CacheError: If cache operation fails
        """
        try:
            # Validate input
            if days < 1 or days > 90:
                raise SchemaValidationError("days must be between 1 and 90")

            cache_key = await self._get_activity_cache_key(days, user_id)

            # Try cache first
            try:
                cached = await self._get_cached_result(cache_key)
                if cached:
                    return cached
            except CacheError as e:
                log.warning(
                    "Cache read failed, proceeding with database query",
                    cache_key=cache_key,
                    error=str(e),
                )

            # Execute query
            result = self._query_user_activity(days, user_id)

            # Update cache
            try:
                self._cache_result(cache_key, result)
            except CacheError as e:
                log.warning("Cache write failed", cache_key=cache_key, error=str(e))

            return result

        except SchemaValidationError:
            raise
        except QueryError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error in user activity summary",
                error=str(e),
                exc_info=True,
                days=days,
                user_id=str(user_id) if user_id else None,
            )
            raise QueryError(f"Failed to get user activity: {str(e)}") from e

    async def get_sales_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get sales performance summary.

        Args:
            days: Number of days to look back (1-365)

        Returns:
            Sales metrics summary

        Raises:
            SchemaValidationError: If input is invalid
            QueryError: If database query fails
        """
        try:
            if days < 1 or days > 365:
                raise SchemaValidationError("days must be between 1 and 365")

            cache_key = f"sales_summary:{days}"

            try:
                cached = await self._get_cached_result(cache_key)
                if cached:
                    return cached
            except CacheError as e:
                log.warning("Cache read failed", cache_key=cache_key, error=str(e))

            result = self._query_sales_summary(days)

            try:
                self._cache_result(cache_key, result)
            except CacheError as e:
                log.warning("Cache write failed", cache_key=cache_key, error=str(e))

            return result

        except SchemaValidationError:
            raise
        except QueryError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error in sales summary",
                error=str(e),
                exc_info=True,
                days=days,
            )
            raise QueryError(f"Failed to get sales summary: {str(e)}") from e

    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get system health metrics.

        Returns:
            System performance metrics

        Raises:
            QueryError: If database query fails
        """
        try:
            cache_key = "system_health:1h"

            try:
                cached = await self._get_cached_result(cache_key)
                if cached:
                    return cached
            except CacheError as e:
                log.warning("Cache read failed", cache_key=cache_key, error=str(e))

            result = self._query_system_health()

            try:
                self._cache_result(cache_key, result)
            except CacheError as e:
                log.warning("Cache write failed", cache_key=cache_key, error=str(e))

            return result

        except QueryError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error in system health", error=str(e), exc_info=True
            )
            raise QueryError(f"Failed to get system health: {str(e)}") from e

    # === PRIVATE HELPERS ===

    def _validate_event_input(self, event_type: str, data: Dict[str, Any]) -> None:
        """Validate event input parameters."""
        if not event_type or not event_type.strip():
            raise SchemaValidationError("event_type is required and cannot be empty")

        if not data:
            raise SchemaValidationError("event data is required")

        if not isinstance(data, dict):
            raise SchemaValidationError("event data must be a dictionary")

        if len(data) == 0:
            raise SchemaValidationError("event data cannot be empty")

    async def _get_activity_cache_key(self, days: int, user_id: Optional[UUID]) -> str:
        """Generate cache key for user activity."""
        if user_id:
            return f"user_activity:{days}d:user_{user_id}"
        return f"user_activity:{days}d:all"

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get result from Redis cache."""
        try:
            if not hasattr(redis_service, "_client") or not redis_service.client:
                raise CacheError("Redis client not initialized")

            cached = await redis_service.client.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError as e:
                    raise CacheError(f"Invalid JSON in cache: {str(e)}") from e
            return None

        except CacheError:
            raise
        except Exception as e:
            log.warning(
                "Unexpected cache read error", cache_key=cache_key, error=str(e)
            )
            raise CacheError(f"Cache read failed: {str(e)}") from e

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Store result in Redis cache."""
        try:
            if not hasattr(redis_service, "_client") or not redis_service.client:
                raise CacheError("Redis client not initialized")

            try:
                serialized = json.dumps(result, default=str)
            except (TypeError, ValueError) as e:
                raise CacheError(f"Failed to serialize result: {str(e)}") from e

            redis_service.client.setex(cache_key, self.cache_ttl, serialized)

        except CacheError:
            raise
        except Exception as e:
            log.warning(
                "Unexpected cache write error", cache_key=cache_key, error=str(e)
            )
            raise CacheError(f"Cache write failed: {str(e)}") from e

    async def _invalidate_event_cache(self, event_type: str) -> None:
        """Invalidate cache for related queries."""
        try:
            if not hasattr(redis_service, "_client") or not redis_service.client:
                raise CacheError("Redis client not initialized")

            # Simple cache invalidation
            patterns = ["user_activity:*", "sales_summary:*", "system_health:*"]

            for pattern in patterns:
                try:
                    keys = await redis_service.client.keys(pattern)
                    if keys:
                        redis_service.client.delete(*keys)
                except Exception as e:
                    log.warning(
                        "Failed to invalidate cache pattern",
                        pattern=pattern,
                        error=str(e),
                    )

        except CacheError:
            raise
        except Exception as e:
            log.warning(
                "Unexpected cache invalidation error",
                event_type=event_type,
                error=str(e),
            )
            raise CacheError(f"Cache invalidation failed: {str(e)}") from e

    def _query_user_activity(
        self, days: int, user_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Execute user activity query."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            # pylint: disable=not-callable
            statement = select(Metrics.metric_type, func.count().label("count")).where(
                Metrics.created_at >= cutoff
            )

            if user_id:
                statement = statement.where(
                    Metrics.value["user_id"].astext == str(user_id)
                )

            statement = statement.group_by(Metrics.metric_type)
            results = self.session.exec(statement).all()

            return {
                "period_days": days,
                "total_events": sum(r[1] for r in results),
                "events_by_type": {
                    metric_type: count for metric_type, count in results
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            log.critical("Failed to query user activity", error=str(e), exc_info=True)
            raise QueryError(f"Database query failed: {str(e)}") from e

    def _query_sales_summary(self, days: int) -> Dict[str, Any]:
        """Execute sales summary query."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            statement = select(
                func.sum(
                    cast(
                        func.jsonb_extract_path_text(Metrics.value, "amount"),
                        Numeric,
                    )
                ),
                # pylint: disable=not-callable
                func.count(),
            ).where(
                Metrics.metric_type == "order.completed", Metrics.created_at >= cutoff
            )

            result = self.session.exec(statement).one()
            total_amount, order_count = result

            return {
                "period_days": days,
                "total_revenue": float(total_amount or 0),
                "orders_count": order_count,
                "average_order_value": float(total_amount or 0) / order_count
                if order_count > 0
                else 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            log.critical("Failed to query sales summary", error=str(e), exc_info=True)
            raise QueryError(f"Database query failed: {str(e)}") from e

    def _query_system_health(self) -> Dict[str, Any]:
        """Execute system health query."""
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            statement = (
                select(
                    Metrics.metric_type,
                    func.avg(
                        cast(
                            func.jsonb_extract_path_text(Metrics.value, "value"),
                            Float,
                        )
                    ),
                    func.max(
                        cast(
                            func.jsonb_extract_path_text(Metrics.value, "value"),
                            Float,
                        )
                    ),
                    func.min(
                        cast(
                            func.jsonb_extract_path_text(Metrics.value, "value"),
                            Float,
                        )
                    ),
                )
                .where(
                    Metrics.metric_type.like("system.%"),  # type: ignore
                    Metrics.created_at >= one_hour_ago,
                )
                .group_by(Metrics.metric_type)
            )

            results = self.session.exec(statement).all()

            metrics = {}
            for metric_type, avg_val, max_val, min_val in results:
                metrics[metric_type] = {
                    "avg": float(avg_val),
                    "max": float(max_val),
                    "min": float(min_val),
                }

            return {
                "period": "1h",
                "metrics": metrics,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            log.critical("Failed to query system health", error=str(e), exc_info=True)
            raise QueryError(f"Database query failed: {str(e)}") from e
