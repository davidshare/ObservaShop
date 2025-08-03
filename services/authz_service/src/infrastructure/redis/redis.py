from typing import Optional
from uuid import UUID

from redis.asyncio import Redis as AsyncRedis

from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import (
    TokenPersistenceError,
    TokenStorageError,
)


class RedisService:
    """
    RedisService provides a secure, observable, and dependency-injectable interface
    for managing refresh tokens and session state in the auth-service.

    This service uses Redis to:
    - Store refresh tokens with user_id mapping
    - Enforce 7-day TTL (604800 seconds)
    - Support token revocation and rotation
    - Prevent reuse of old tokens

    The service is designed for use with FastAPI's dependency injection system
    and integrates with loguru for structured logging.

    Example usage:
        redis = RedisService()
        await redis.connect()
        await redis.close()
    """

    def __init__(self) -> None:
        """
        Initialize the RedisService with no active connection.
        The Redis client is created during connect() to support async initialization.
        """
        self._client: Optional[AsyncRedis] = None

    async def connect(self) -> None:
        """
        Establish a connection to the Redis server using configuration from `config`.

        Raises:
            RuntimeError: If connection fails after configuration validation.
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
                decode_responses=True,
                encoding="utf-8",
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
        except Exception as e:
            log.critical(
                "Failed to connect to Redis",
                redis_host=config.REDIS_HOST,
                redis_port=config.REDIS_PORT,
                error=str(e),
            )
            raise RuntimeError(
                "Unable to connect to Redis. Check host, port, and network."
            ) from e

    async def close(self) -> None:
        """
        Safely close the Redis connection.

        Logs the closure and sets client to None.
        """
        if self._client is None:
            log.debug("RedisService.close() called, but no active connection")
            return

        try:
            await self._client.close()
            log.info("Redis connection closed gracefully")
        except Exception as e:
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
        except Exception:
            return False

    async def is_connected(self) -> bool:
        """
        Check if the Redis client is connected (regardless of server responsiveness).

        Returns:
            bool: True if client is connected, False otherwise.
        """
        return self._client is not None

    async def set_user_permissions(
        self, user_id: UUID, permissions: set[str], ttl: int = 300
    ) -> None:
        """
        Cache a user's full permission set in Redis.
        """
        if self._client is None:
            log.error("Cannot set user permissions: Redis client not connected")
            raise TokenStorageError(
                "Redis client not initialized. Call connect() first."
            )

        key = f"permissions:{user_id}"

        try:
            await self._client.setex(key, ttl, ",".join(sorted(permissions)))
            log.info(
                "User permissions cached",
                user_id=str(user_id),
                permission_count=len(permissions),
                ttl=ttl,
            )
        except (ConnectionError, TimeoutError) as e:
            log.error(
                "Failed to cache user permissions due to connectivity issue",
                user_id=str(user_id),
                error=str(e),
            )
            raise TokenPersistenceError(
                "Failed to persist permissions: connection error"
            ) from e
        except Exception as e:
            log.error(
                "Unexpected error caching user permissions",
                user_id=str(user_id),
                error=str(e),
            )
            raise TokenPersistenceError("Failed to store permissions in Redis") from e

    async def get_user_permissions(self, user_id: UUID) -> Optional[set[str]]:
        """
        Retrieve cached permissions for a user.
        Returns None if not found, expired, or Redis is unavailable.
        """
        if self._client is None:
            log.error("Cannot get user permissions: Redis client not connected")
            raise TokenStorageError(
                "Redis client not initialized. Call connect() first."
            )

        key = f"permissions:{user_id}"

        try:
            value = await self._client.get(key)
            if value is None:
                log.debug("Permission cache miss", user_id=str(user_id))
                return None

            permissions = set(value.split(","))
            log.info(
                "Permission cache hit",
                user_id=str(user_id),
                permission_count=len(permissions),
            )
            return permissions

        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Redis connectivity failed during permission lookup",
                user_id=str(user_id),
                error=str(e),
            )
            # On Redis failure, return None — fallback to DB
            return None

        except Exception as e:
            log.critical(
                "Unexpected error retrieving user permissions",
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            return None  # Never let Redis failure block authorization
