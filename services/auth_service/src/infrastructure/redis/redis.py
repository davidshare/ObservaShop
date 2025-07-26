# src/infrastructure/redis/redis.py

from typing import Optional
from uuid import UUID

from loguru import logger
from redis.asyncio import Redis as AsyncRedis

from src.config.config import config
from src.core.exceptions import (
    TokenDeserializationError,
    TokenPersistenceError,
    TokenStorageError,
    TokenNotFoundError,
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
        await redis.set_refresh_token(token, user_id)
        user_id = await redis.get_refresh_token(token)
        await redis.delete_refresh_token(token)
        await redis.close()
    """

    def __init__(self) -> None:
        """Initialize the RedisService with no active connection."""
        self._client: Optional[AsyncRedis] = None

    async def connect(self) -> None:
        """
        Establish a connection to the Redis server using configuration from `config`.

        Raises:
            RuntimeError: If connection fails after configuration validation.
        """
        if self._client is not None:
            logger.warning(
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
            logger.info(
                "Connected to Redis",
                redis_host=config.REDIS_HOST,
                redis_port=config.REDIS_PORT,
                redis_db=config.REDIS_DB,
            )
        except Exception as e:
            logger.critical(
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
            logger.debug("RedisService.close() called, but no active connection")
            return

        try:
            await self._client.close()
            logger.info("Redis connection closed gracefully")
        except Exception as e:
            logger.error("Error during Redis connection close", error=str(e))
        finally:
            self._client = None

    async def set_refresh_token(
        self, token: str, user_id: UUID, ttl: Optional[int] = None
    ) -> None:
        """
        Store a refresh token in Redis with a TTL, mapping it to a user_id.

        Args:
            token: The JWT refresh token string (without 'Bearer ' prefix).
            user_id: The UUID of the associated user.
            ttl: Time-to-live in seconds. Defaults to config.REDIS_TTL (7 days).

        Raises:
            TokenPersistenceError: If Redis client is not connected or operation fails.
        """
        if self._client is None:
            logger.error("Cannot set refresh token: Redis client not connected")
            raise TokenPersistenceError(
                "Redis client not initialized. Call connect() first."
            )

        actual_ttl = ttl if ttl is not None else config.REDIS_TTL
        key = f"refresh_token:{token}"

        try:
            await self._client.setex(key, actual_ttl, str(user_id))
            logger.info(
                "Refresh token stored",
                user_id=str(user_id),
                token_hash=hash(token) % 10**8,
                ttl=actual_ttl,
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                "Failed to store refresh token due to connectivity issue",
                user_id=str(user_id),
                error=str(e),
            )
            raise TokenPersistenceError(
                "Failed to persist refresh token: connection error"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error storing refresh token",
                user_id=str(user_id),
                error=str(e),
            )
            raise TokenPersistenceError("Failed to store refresh token in Redis") from e

    async def get_refresh_token(self, token: str) -> UUID:
        """
        Retrieve the user_id associated with a refresh token.

        Args:
            token: The JWT refresh token string.

        Returns:
            UUID of the user.

        Raises:
            TokenNotFoundError: If token is not found in Redis.
            TokenDeserializationError: If stored user_id is invalid UUID format.
            TokenStorageError: If Redis connection fails.
        """
        if self._client is None:
            logger.error("Cannot get refresh token: Redis client not connected")
            raise TokenStorageError(
                "Redis client not initialized. Call connect() first."
            )

        key = f"refresh_token:{token}"
        try:
            user_id_str = await self._client.get(key)
            if user_id_str is None:
                logger.info(
                    "Refresh token not found",
                    token_hash=hash(token) % 10**8,
                )
                raise TokenNotFoundError(f"Refresh token {token} not found in Redis")

            try:
                user_id = UUID(user_id_str)
                logger.info(
                    "Refresh token found",
                    user_id=str(user_id),
                    token_hash=hash(token) % 10**8,
                )
                return user_id
            except ValueError as e:
                logger.error(
                    "Invalid UUID format retrieved from Redis",
                    raw_value=user_id_str,
                    token_hash=hash(token) % 10**8,
                )
                raise TokenDeserializationError(
                    f"Stored user_id for token is invalid UUID: {user_id_str}"
                ) from e

        except (ConnectionError, TimeoutError) as e:
            logger.critical(
                "Redis connectivity failed during token lookup",
                token_hash=hash(token) % 10**8,
                error=str(e),
            )
            raise TokenStorageError("Failed to connect to Redis") from e
        except Exception as e:
            logger.critical(
                "Unexpected error retrieving refresh token",
                token_hash=hash(token) % 10**8,
                error=str(e),
            )
            raise TokenStorageError("Internal Redis error") from e

    async def delete_refresh_token(self, token: str) -> None:
        """
        Remove a refresh token from Redis (e.g., on logout or rotation).

        Args:
            token: The JWT refresh token string.

        Raises:
            TokenStorageError: If Redis client is not connected.
        """
        if self._client is None:
            logger.error("Cannot delete refresh token: Redis client not connected")
            raise TokenStorageError(
                "Redis client not initialized. Call connect() first."
            )

        key = f"refresh_token:{token}"
        try:
            deleted_count = await self._client.delete(key)
            if deleted_count > 0:
                logger.info(
                    "Refresh token deleted",
                    token_hash=hash(token) % 10**8,
                )
            else:
                logger.debug(
                    "No refresh token found to delete",
                    token_hash=hash(token) % 10**8,
                )
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                "Failed to delete refresh token due to connectivity issue",
                token_hash=hash(token) % 10**8,
                error=str(e),
            )
            raise TokenStorageError(
                "Failed to delete refresh token: connection error"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error deleting refresh token",
                token_hash=hash(token) % 10**8,
                error=str(e),
            )
            raise TokenStorageError("Failed to delete refresh token") from e
