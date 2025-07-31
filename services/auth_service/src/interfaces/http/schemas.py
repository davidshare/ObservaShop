from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """
    Schema for user registration input.
    """

    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[datetime] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """
        Validate password strength.

        Args:
            value: The password string.

        Returns:
            The validated password.

        Raises:
            ValueError: If password does not meet requirements.
        """
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        return value


class UserResponse(BaseModel):
    """
    Schema for user output (excludes sensitive fields like hashed_password).
    """

    id: UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # For ORM mode


class UserLogin(BaseModel):
    """
    Schema for user login input.
    """

    email: str
    password: str


class TokenResponse(BaseModel):
    """
    Schema for JWT token response.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds


class RefreshTokenRequest(BaseModel):
    """
    Schema for refresh token request.
    """

    refresh_token: str

    model_config = {"extra": "forbid"}
