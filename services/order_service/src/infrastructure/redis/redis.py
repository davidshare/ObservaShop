from typing import Optional, Dict, Any
from uuid import UUID
from redis.asyncio import Redis as AsyncRedis
from src.config.config import config
from src.config.logger_config import log


class RedisService:
    """
    RedisService provides a secure, observable, and dependency-injectable interface
    for managing refresh tokens and session state in the authz-service.

    This service uses Redis to:
    - Cache user permission sets with superadmin flag
    - Support fast authorization checks
    - Prevent service disruption on Redis failure (fail-soft)

    The service is designed for use with FastAPI's dependency injection system
    and integrates with loguru for structured logging.
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
            log.exception(
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
        self, user_id: UUID, data: Dict[str, Any], ttl: int = None
    ) -> None:
        """
        Cache a user's full permission set and superadmin status in Redis.
        Data should be: {"permissions": set[str], "is_superadmin": bool}
        """
        if self._client is None:
            log.error("Cannot set user permissions: Redis client not connected")
            # Fail-soft: do not raise, just return
            return

        actual_ttl = ttl if ttl is not None else config.REDIS_TTL
        key = f"permissions:{user_id}"

        try:
            import json

            value = json.dumps(
                {
                    "permissions": list(data.get("permissions", [])),
                    "is_superadmin": data.get("is_superadmin", False),
                }
            )
            await self._client.setex(key, actual_ttl, value)
            log.info(
                "User permissions cached",
                user_id=str(user_id),
                permission_count=len(data.get("permissions", [])),
                is_superadmin=data.get("is_superadmin", False),
                ttl=actual_ttl,
            )
        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Failed to cache user permissions due to connectivity issue",
                user_id=str(user_id),
                error=str(e),
            )
            # Fail-soft: do not raise
            return
        except Exception as e:
            log.error(
                "Unexpected error caching user permissions",
                user_id=str(user_id),
                error=str(e),
            )
            # Fail-soft: do not raise
            return

    async def get_user_permissions(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached permissions and superadmin status for a user.
        Returns a dict: {"permissions": set[str], "is_superadmin": bool}
        Returns None if not found, expired, or Redis is unavailable.
        """
        if self._client is None:
            log.warning("Cannot get user permissions: Redis client not connected")
            # Fail-soft: return None, fallback to DB
            return None

        key = f"permissions:{user_id}"

        try:
            value = await self._client.get(key)
            if value is None:
                log.debug("Permission cache miss", user_id=str(user_id))
                return None

            import json

            data = json.loads(value)
            result = {
                "permissions": set(data.get("permissions", [])),
                "is_superadmin": data.get("is_superadmin", False),
            }
            log.info(
                "Permission cache hit",
                user_id=str(user_id),
                permission_count=len(result["permissions"]),
                is_superadmin=result["is_superadmin"],
            )
            return result

        except (ConnectionError, TimeoutError) as e:
            log.warning(
                "Redis connectivity failed during permission lookup",
                user_id=str(user_id),
                error=str(e),
            )
            # Fail-soft: return None, fallback to DB
            return None

        except Exception as e:
            log.exception(
                "Unexpected error retrieving user permissions",
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            # Fail-soft: never let Redis failure block authorization
            return None
