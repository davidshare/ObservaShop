from typing import Optional


class CategoryError(Exception):
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
class TokenError(CategoryError):
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
# Category-related errors
# ------------------------


class CategoryNotFoundError(CategoryError):
    """
    Raised when a category with the given ID or name does not exist.
    Used in category_service when a category is not found in the database.
    """

    pass


class CategoryAlreadyExistsError(CategoryError):
    """
    Raised when trying to create a category with a name that already exists.
    Prevents duplicate category names.
    """

    pass


class CategoryHierarchyError(CategoryError):
    """
    Raised when a category hierarchy operation would create a cycle (e.g., a parent becomes its own descendant).
    Indicates invalid input or attempted self-reference.
    """

    pass


class InvalidInputError(CategoryError):
    """
    Raised when a invalid input is passed.
    """

    pass


class DatabaseError(CategoryError):
    """
    Raised when a there is a database error.
    """

    pass


###### Products


class ProductError(Exception):
    """
    Base class for all product errors in the product service.
    Should not be exposed directly to the client — convert to HTTPException.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


class ProductNotFoundError(ProductError):
    """Raised when a product with the given ID does not exist or is inactive."""

    pass


class ProductAlreadyExistsError(ProductError):
    """Raised when trying to create a product with a name that already exists."""

    pass
