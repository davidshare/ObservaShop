class AuthServiceError(Exception):
    """Base exception for all authentication service errors."""

    pass


# ------------------------
# Token-related errors
# ------------------------
class TokenError(AuthServiceError):
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


class TokenRevokedError(TokenError):
    """Raised when a valid token has been revoked (e.g., logout)."""

    pass


class TokenStorageError(TokenError):
    """Raised when there is a problem with token storage (Redis)."""

    pass


class TokenNotFoundError(TokenStorageError):
    """Raised when a token is not found in Redis (could be expired or deleted)."""

    pass


class TokenDeserializationError(TokenStorageError):
    """Raised when data retrieved from Redis cannot be parsed (e.g., invalid UUID)."""

    pass


class TokenPersistenceError(TokenStorageError):
    """Raised when Redis write fails (network, timeout, etc.)."""

    pass


# ------------------------
# User-related errors
# ------------------------
class UserError(AuthServiceError):
    """Base class for user-related failures."""

    pass


class UserNotFoundError(UserError):
    """Raised when a user does not exist."""

    pass


class UserAlreadyExistsError(UserError):
    """Raised when trying to create a user that already exists."""

    pass


class UserInactiveError(UserError):
    """Raised when an inactive user tries to authenticate."""

    pass


# ------------------------
# Authentication/Authorization
# ------------------------
class AuthenticationError(AuthServiceError):
    """Base class for authentication failures."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when username or password is incorrect."""

    pass


class MFARequiredError(AuthenticationError):
    """Raised when MFA is required but not provided."""

    pass


class AuthorizationError(AuthServiceError):
    """User is authenticated but not authorized to perform the action."""

    pass


class PermissionDeniedError(AuthorizationError):
    """User lacks required permissions."""

    pass


# ------------------------
# OTP / MFA
# ------------------------
class OTPError(AuthServiceError):
    """Base class for one-time password errors."""

    pass


class OTPExpiredError(OTPError):
    """The OTP has expired."""

    pass


class OTPInvalidError(OTPError):
    """The OTP is invalid or incorrect."""

    pass


# ------------------------
# Rate Limiting
# ------------------------
class RateLimitError(AuthServiceError):
    """Base class for rate-limiting errors."""

    pass


class TooManyAttemptsError(RateLimitError):
    """Too many failed login attempts."""

    pass
