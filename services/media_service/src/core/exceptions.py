# ------------------------
# Base Media Exception
# ------------------------


class MediaError(Exception):
    """Base exception for media-related errors."""

    pass


class MediaNotFoundError(MediaError):
    """Raised when a media asset is not found."""

    def __init__(self, media_id: str):
        super().__init__(f"Media with ID {media_id} not found")
        self.media_id = media_id


class MediaUploadError(MediaError):
    """Raised when media upload fails."""

    def __init__(self, message: str = "Media upload failed"):
        super().__init__(message)
        self.message = message


class InvalidMediaError(MediaError):
    """Raised when media validation fails (e.g., wrong file type)."""

    def __init__(self, message: str = "Invalid media data"):
        super().__init__(message)
        self.message = message


class MediaAccessDeniedError(MediaError):
    """Raised when user is not authorized to access media."""

    def __init__(self, media_id: str):
        super().__init__(f"Access denied to media {media_id}")
        self.media_id = media_id


class MediaDeletionError(MediaError):
    """Raised when media deletion fails."""

    def __init__(self, media_id: str, reason: str = "Unknown reason"):
        super().__init__(f"Failed to delete media {media_id}: {reason}")
        self.media_id = media_id
        self.reason = reason


# ------------------------
# Domain & Input Errors
# ------------------------


class InvalidInputError(Exception):
    """
    Raised when invalid input is passed.
    """

    def __init__(self, message: str = "Invalid input provided"):
        super().__init__(message)
        self.message = message


class DatabaseError(Exception):
    """
    Raised when there is an error with the database.
    """

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)
        self.message = message


class ExternalServiceError(Exception):
    """
    Raised when there is an unexpected error from an external service.
    """

    def __init__(self, service_name: str, message: str = "Service call failed"):
        super().__init__(f"{service_name} error: {message}")
        self.service_name = service_name
        self.message = message


# ------------------------
# Token-related errors
# ------------------------


class TokenError(Exception):
    """Base class for token-related failures."""

    pass


class TokenExpiredError(TokenError):
    """Raised when a token's expiration time has passed."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message)
        self.message = message


class TokenInvalidError(TokenError):
    """Raised when a token is malformed or has an invalid signature."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)
        self.message = message


class TokenMissingClaimError(TokenError):
    """Raised when a required claim (e.g. 'sub') is missing."""

    def __init__(self, claim: str):
        super().__init__(f"Missing required claim: {claim}")
        self.claim = claim
