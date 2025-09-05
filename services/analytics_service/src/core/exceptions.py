from typing import Optional


class PaymentError(Exception):
    """
    Base class for all Category errors in the product service.
    Should not be exposed directly to the client — convert to HTTPException.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


# ------------------------
# Token-related errors
# ------------------------
class TokenError(PaymentError):
    """Base class for token-related failures."""

    pass


class TokenExpiredError(TokenError):
    """Raised when a token's expiration time has passed."""

    pass


class TokenInvalidError(TokenError):
    """Raised when a token is malformed or has an invalid signature."""

    pass


class TokenMissingClaimError(TokenError):
    """Raised when a required claim (e.g. 'sub') is missing."""

    pass


class TokenStorageError(TokenError):
    """Raised when there is a problem with token storage (Redis)."""

    pass


class TokenPersistenceError(TokenStorageError):
    """Raised when Redis write fails (network, timeout, etc.)."""

    pass


class InvalidInputError(PaymentError):
    """
    Raised when a invalid input is passed.
    """

    pass


class DatabaseError(PaymentError):
    """
    Raised when a there is a database error.
    """

    pass


##### Orders/OrderItems


class OrderNotFoundError(PaymentError):
    """Raised when an order with the given ID does not exist or the user is not authorized to access it."""

    pass


class OrderStatusTransitionError(PaymentError):
    """
    Raised when an order with the given ID does not exist
    or the user is not authorized to access it.
    """

    pass


class PaymentProcessingError(Exception):
    """
    Raised when payment service fails to process a payment.
    Should be mapped to 400 Bad Request or 502 Bad Gateway.
    """

    pass


class PaymentNotFoundError(PaymentError):
    """Raised when a payment with the given ID does not exist or the user is not authorized to access it."""

    pass


class PaymentAlreadyExistsError(PaymentError):
    """Raised when trying to create a payment that already exists (e.g., duplicate idempotency key)."""

    pass


class IdempotencyError(PaymentError):
    """Raised when an idempotency key is reused for a different request."""

    pass


class InsufficientStockError(PaymentError):
    """Raised when a product stock is insufficient."""

    pass


### Redis errors


class RedisConnectionError(Exception):
    """Raised when the service cannot connect to the Redis server."""

    pass


class RedisPingError(Exception):
    """Raised when there is an error pinging the redis service"""

    pass


class RedisConnectionCloseError(Exception):
    """Raised when there is an issue closing the redis connection"""

    pass


class RedisInitializationError(Exception):
    """Raised when Redis client fails to initialize due to configuration or unexpected errors."""

    pass


class RedisOperationError(Exception):
    """Raised when a Redis operation (SET, GET, DELETE) fails after connection."""

    pass


class RedisSerializationError(Exception):
    """Raised when data cannot be serialized for Redis storage."""

    pass


class RedisDeserializationError(Exception):
    """Raised when cached data cannot be deserialized (e.g., corrupted JSON)."""

    pass


class RedisCacheInvalidationError(Exception):
    """Raised when cached data cannot be invalidated."""

    pass


class ExternalServiceError(Exception):
    """Raised when a downstream service (e.g., order-service, Kafka) is unreachable."""

    def __init__(
        self, service_name: str, message: str, original_exception: Exception = None
    ):
        super().__init__(f"{service_name} error: {message}")
        self.service_name = service_name
        self.message = message
        self.original_exception = original_exception


class SchemaValidationError(Exception):
    pass


class CacheError(Exception):
    pass


class EventProcessingError(Exception):
    pass


class NotFoundError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class ValidationError(Exception):
    pass


class QueryError(Exception):
    pass
