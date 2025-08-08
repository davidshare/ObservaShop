from typing import Optional


class OrderError(Exception):
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
class TokenError(OrderError):
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


class InvalidInputError(OrderError):
    """
    Raised when a invalid input is passed.
    """

    pass


class DatabaseError(OrderError):
    """
    Raised when a there is a database error.
    """

    pass
