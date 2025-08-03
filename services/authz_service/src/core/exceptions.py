from typing import Optional


class AuthorizationError(Exception):
    """
    Raised when an authorization check fails due to internal error or misconfiguration.
    Should not be exposed directly to the client — convert to HTTPException.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


# ------------------------
# Token-related errors
# ------------------------
class TokenError(AuthorizationError):
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


# ------------------------
# Role-related errors
# ------------------------
class RoleNotFoundError(Exception):
    """
    Raised when a role with the given ID does not exist.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RoleAlreadyExistsError(Exception):
    """
    Raised when trying to create a role with a name that already exists.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermissionNotFoundError(Exception):
    """
    Raised when a permission with the given ID does not exist.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermissionAlreadyExistsError(Exception):
    """
    Raised when trying to create a permission with a name that already exists.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UserRoleAlreadyExistsError(Exception):
    """
    Raised when trying to assign a role to a user who already has it.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UserRoleNotFoundError(Exception):
    """
    Raised when a user-role assignment does not exist.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
