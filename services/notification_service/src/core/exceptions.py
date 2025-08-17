class NotificationError(Exception):
    """Base exception for all notification-related errors"""

    pass


class NotificationNotFoundError(NotificationError):
    """Raised when a notification with the given ID is not found"""

    def __init__(self, notification_id: str):
        super().__init__(f"Notification with ID {notification_id} not found")
        self.notification_id = notification_id


class NotificationCreationError(NotificationError):
    """Raised when notification creation fails"""

    def __init__(self, message: str = "Failed to create notification"):
        super().__init__(message)
        self.message = message


class NotificationUpdateError(NotificationError):
    """Raised when notification update fails"""

    def __init__(self, message: str = "Failed to update notification"):
        super().__init__(message)
        self.message = message


class NotificationDeletionError(NotificationError):
    """Raised when notification deletion fails"""

    def __init__(self, message: str = "Failed to delete notification"):
        super().__init__(message)
        self.message = message


class NotificationSendError(NotificationError):
    """Raised when sending a notification fails"""

    def __init__(self, recipient: str, channel: str, error: str):
        super().__init__(
            f"Failed to send {channel} notification to {recipient}: {error}"
        )
        self.recipient = recipient
        self.channel = channel
        self.error = error


class EmailSendError(NotificationSendError):
    """Raised when sending an email notification fails"""

    def __init__(self, email: str, error: str):
        super().__init__(recipient=email, channel="email", error=error)
        self.email = email


class SMSSendError(NotificationSendError):
    """Raised when sending an SMS notification fails"""

    def __init__(self, phone: str, error: str):
        super().__init__(recipient=phone, channel="sms", error=error)
        self.phone = phone


class InvalidNotificationError(NotificationError):
    """Raised when notification data is invalid"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidEmailError(InvalidNotificationError):
    """Raised when email address is invalid"""

    def __init__(self, email: str):
        super().__init__(f"Invalid email address: {email}")
        self.email = email


class InvalidPhoneError(InvalidNotificationError):
    """Raised when phone number is invalid"""

    def __init__(self, phone: str):
        super().__init__(f"Invalid phone number: {phone}")
        self.phone = phone


class InvalidNotificationTypeError(InvalidNotificationError):
    """Raised when notification type is not supported"""

    def __init__(self, notification_type: str):
        super().__init__(f"Unsupported notification type: {notification_type}")
        self.notification_type = notification_type


class EventProcessingError(NotificationError):
    """Raised when processing a Kafka event fails"""

    def __init__(self, event_type: str, error: str):
        super().__init__(f"Failed to process event {event_type}: {error}")
        self.event_type = event_type
        self.error = error


class KafkaConsumerError(NotificationError):
    """Raised when Kafka consumer encounters an error"""

    def __init__(self, error: str):
        super().__init__(f"Kafka consumer error: {error}")
        self.error = error


class EmailConfigurationError(NotificationError):
    """Raised when email configuration is missing or invalid"""

    def __init__(self, missing_field: str):
        super().__init__(f"Email configuration error: missing {missing_field}")
        self.missing_field = missing_field


class DatabaseError(NotificationError):
    """Raised when there is an error with the database"""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)
        self.message = message


class ExternalServiceError(NotificationError):
    """Raised when there is an unexpected error from an external service"""

    def __init__(self, service_name: str, message: str):
        super().__init__(f"{service_name} error: {message}")
        self.service_name = service_name
        self.message = message


class PermissionDeniedError(NotificationError):
    """Raised when user is not authorized to perform an action"""

    def __init__(self, action: str, user_id: str = ""):
        message = f"Permission denied: {action}"
        if user_id:
            message += f" for user {user_id}"
        super().__init__(message)
        self.action = action
        self.user_id = user_id


class RateLimitExceededError(NotificationError):
    """Raised when notification rate limit is exceeded"""

    def __init__(self, recipient: str, limit: int, period: str):
        super().__init__(
            f"Rate limit exceeded for {recipient}: {limit} notifications per {period}"
        )
        self.recipient = recipient
        self.limit = limit
        self.period = period


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


# ------------------------
# Token-related errors
# ------------------------
class TokenError(Exception):
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
