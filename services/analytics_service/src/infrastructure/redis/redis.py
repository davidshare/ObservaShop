import json
from typing import Any, Dict, Optional
from uuid import UUID

from redis.asyncio import Redis as AsyncRedis

from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import (
    RedisConnectionError,
    RedisDeserializationError,
    RedisInitializationError,
    RedisOperationError,
    RedisSerializationError,
    RedisConnectionCloseError,
    RedisPingError,
    RedisCacheInvalidationError,
)


class RedisService:
    """
    RedisService provides a secure, observable, and dependency-injectable interface
    for caching product and order data in the order-service.

    This service uses Redis to:
    - Cache product details from product-service (reducing latency and load)
    - Cache order responses for fast reads (e.g., admin dashboards)
    - Support fast read operations with TTL-based invalidation
    - Fail-soft: if Redis is down, fall back to direct database/service calls

    The service is designed for use with FastAPI's dependency injection system
    and integrates with loguru for structured logging.

    Example usage:
        redis = RedisService()
        await redis.connect()
        await redis.set_product(product_id, product_data)
        data = await redis.get_product(product_id)
        await redis.close()
    """

    def __init__(self) -> None:
        """
        Initialize the RedisService with no active connection.
        The Redis client is created during connect() to support async initialization.
        """
        self._client: Optional[AsyncRedis] = None

    @property
    def client(self) -> Optional[AsyncRedis]:
        """Public access to the Redis client."""
        return self._client

    async def connect(self) -> None:
        """
        Establish a connection to the Redis server using configuration from `config`.

        Raises:
            RedisConnectionError: If connection fails after configuration validation.
        """
        if self._client is not None:
            log.warning(
                "RedisService.connect() called, but client is already connected"
            )
            return

        try:
            self._client = AsyncRedis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                decode_responses=False,  # Keep binary for performance
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._client.ping()
            log.info(
                "Connected to Redis",
                redis_host=config.REDIS_HOST,
                redis_port=config.REDIS_PORT,
                redis_db=config.REDIS_DB,
            )
        except (ConnectionError, TimeoutError) as e:
            log.exception(
                "Failed to connect to Redis: connection or timeout error",
                redis_host=config.REDIS_HOST,
                redis_port=config.REDIS_PORT,
                error=str(e),
            )
            raise RedisConnectionError(
                f"Unable to connect to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}. "
                "Check host, port, network, and firewall settings."
            ) from e
        except Exception as e:
            log.exception(
                "Failed to connect to Redis: unexpected error",
                redis_host=config.REDIS_HOST,
                redis_port=config.REDIS_PORT,
                error=str(e),
            )
            raise RedisInitializationError(
                "Unexpected error during Redis initialization. "
                "Check Redis server status and configuration."
            ) from e

    async def close(self) -> None:
        """
        Safely close the Redis connection.

        Logs the closure and sets client to None.
        Does not raise exceptions to avoid blocking shutdown.
        """
        if self._client is None:
            log.debug("RedisService.close() called, but no active connection")
            return

        try:
            await self._client.close()
            log.info("Redis connection closed gracefully")
        except RedisConnectionCloseError as e:
            log.error("Error during Redis connection close", error=str(e))
        finally:
            self._client = None

    async def ping(self) -> bool:
        """
        Check if Redis is responsive.

        Returns:
            bool: True if Redis is connected and responsive, False otherwise.
        """
        if self._client is None:
            return False
        try:
            await self._client.ping()
            return True
        except RedisPingError:
            return False

    async def is_connected(self) -> bool:
        """
        Check if the Redis client is connected (regardless of server responsiveness).

        Returns:
            bool: True if client is connected, False otherwise.
        """
        return self._client is not None

    async def set_product(
        self, product_id: UUID, data: Dict[str, Any], ttl: int = None
    ) -> None:
        """
        Cache product data retrieved from product-service.
        Data should be the full product response (id, name, price, stock, etc.)

        Args:
            product_id: UUID of the product to cache.
            data: Product data to store in Redis.
            ttl: Time-to-live in seconds. Uses default if None.

        Raises:
            RedisConnectionError: If Redis is unreachable.
            RedisSerializationError: If data cannot be serialized.
        """
        if self._client is None:
            log.warning("Cannot set product cache: Redis client not connected")
            return  # Fail-soft

        actual_ttl = ttl if ttl is not None else 300  # Default 5 minutes
        key = f"product:{product_id}"

        try:
            value = json.dumps(data)
            await self._client.setex(key, actual_ttl, value)
            log.info("Product cached", product_id=str(product_id), ttl=actual_ttl)
        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Failed to cache product due to connectivity issue",
                product_id=str(product_id),
                error=str(e),
            )
            # Fail-soft: do not raise
            return
        except (TypeError, ValueError) as e:
            log.error(
                "Failed to serialize product data",
                product_id=str(product_id),
                error=str(e),
            )
            raise RedisSerializationError(
                f"Failed to serialize product {product_id} for Redis storage."
            ) from e
        except Exception as e:
            log.error(
                "Unexpected error caching product",
                product_id=str(product_id),
                error=str(e),
            )
            raise RedisOperationError(
                f"Unexpected error during Redis SET operation for product {product_id}."
            ) from e

    async def get_product(self, product_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached product data.
        Returns the product dict or None if not found, expired, or Redis is unavailable.

        Args:
            product_id: UUID of the product to retrieve.

        Returns:
            Product data dict or None if not found or Redis unavailable.

        Raises:
            RedisConnectionError: If Redis is unreachable.
            RedisDeserializationError: If cached data is corrupted.
        """
        if self._client is None:
            log.warning("Cannot get product from cache: Redis client not connected")
            return None

        key = f"product:{product_id}"
        try:
            value = await self._client.get(key)
            if value is None:
                log.debug("Product cache miss", product_id=str(product_id))
                return None

            data = json.loads(value)
            log.info("Product cache hit", product_id=str(product_id))
            return data
        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Redis connectivity failed during product lookup",
                product_id=str(product_id),
                error=str(e),
            )
            return None
        except (json.JSONDecodeError, TypeError) as e:
            log.error(
                "Corrupted product data in Redis",
                product_id=str(product_id),
                error=str(e),
            )
            raise RedisDeserializationError(
                f"Corrupted data for product {product_id} in Redis cache."
            ) from e
        except Exception as e:
            log.exception(
                "Unexpected error retrieving product from cache",
                product_id=str(product_id),
                error=str(e),
            )
            raise RedisOperationError(
                f"Unexpected error during Redis GET operation for product {product_id}."
            ) from e

    async def set_order(
        self, order_id: UUID, data: Dict[str, Any], ttl: int = None
    ) -> None:
        """
        Cache order response data.
        Useful for admin dashboards or frequently accessed orders.

        Args:
            order_id: UUID of the order to cache.
            data: Order data to store.
            ttl: Time-to-live in seconds.

        Raises:
            RedisConnectionError: If Redis is unreachable.
            RedisSerializationError: If data cannot be serialized.
        """
        if self._client is None:
            log.warning("Cannot set order cache: Redis client not connected")
            return

        actual_ttl = ttl if ttl is not None else 600  # Default 10 minutes
        key = f"order:{order_id}"

        try:
            value = json.dumps(data)
            await self._client.setex(key, actual_ttl, value)
            log.info("Order cached", order_id=str(order_id), ttl=actual_ttl)
        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Failed to cache order due to connectivity issue",
                order_id=str(order_id),
                error=str(e),
            )
            return
        except (TypeError, ValueError) as e:
            log.error(
                "Failed to serialize order data",
                order_id=str(order_id),
                error=str(e),
            )
            raise RedisSerializationError(
                f"Failed to serialize order {order_id} for Redis storage."
            ) from e
        except Exception as e:
            log.error(
                "Unexpected error caching order",
                order_id=str(order_id),
                error=str(e),
            )
            raise RedisOperationError(
                f"Unexpected error during Redis SET operation for order {order_id}."
            ) from e

    async def get_order(self, order_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached order data.
        Returns the order dict or None if not found, expired, or Redis is unavailable.

        Args:
            order_id: UUID of the order to retrieve.

        Returns:
            Order data dict or None if not found or Redis unavailable.

        Raises:
            RedisConnectionError: If Redis is unreachable.
            RedisDeserializationError: If cached data is corrupted.
        """
        if self._client is None:
            log.warning("Cannot get order from cache: Redis client not connected")
            return None

        key = f"order:{order_id}"
        try:
            value = await self._client.get(key)
            if value is None:
                log.debug("Order cache miss", order_id=str(order_id))
                return None

            data = json.loads(value)
            log.info("Order cache hit", order_id=str(order_id))
            return data
        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Redis connectivity failed during order lookup",
                order_id=str(order_id),
                error=str(e),
            )
            return None
        except (json.JSONDecodeError, TypeError) as e:
            log.error(
                "Corrupted order data in Redis",
                order_id=str(order_id),
                error=str(e),
            )
            raise RedisDeserializationError(
                f"Corrupted data for order {order_id} in Redis cache."
            ) from e
        except Exception as e:
            log.exception(
                "Unexpected error retrieving order from cache",
                order_id=str(order_id),
                error=str(e),
            )
            raise RedisOperationError(
                f"Unexpected error during Redis GET operation for order {order_id}."
            ) from e

    async def invalidate_product(self, product_id: UUID) -> None:
        """
        Invalidate the cache for a specific product (e.g., after stock update).
        Safe to call even if key doesn't exist.

        Args:
            product_id: UUID of the product to invalidate.
        """
        if self._client is None:
            return
        key = f"product:{product_id}"
        try:
            deleted_count = await self._client.delete(key)
            if deleted_count > 0:
                log.info("Product cache invalidated", product_id=str(product_id))
            else:
                log.debug(
                    "No product cache found to invalidate", product_id=str(product_id)
                )
        except RedisCacheInvalidationError as e:
            log.warning(
                "Failed to invalidate product cache",
                product_id=str(product_id),
                error=str(e),
            )

    async def invalidate_order(self, order_id: UUID) -> None:
        """
        Invalidate the cache for a specific order (e.g., after status update).
        Safe to call even if key doesn't exist.

        Args:
            order_id: UUID of the order to invalidate.
        """
        if self._client is None:
            return
        key = f"order:{order_id}"
        try:
            deleted_count = await self._client.delete(key)
            if deleted_count > 0:
                log.info("Order cache invalidated", order_id=str(order_id))
            else:
                log.debug("No order cache found to invalidate", order_id=str(order_id))
        except RedisCacheInvalidationError as e:
            log.warning(
                "Failed to invalidate order cache",
                order_id=str(order_id),
                error=str(e),
            )

    def redis_client(self):
        "return the private variable redis client"

        return self._client
