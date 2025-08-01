from datetime import datetime
from typing import Optional, List
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


class UserUpdate(BaseModel):
    """
    Schema for updating user profile.
    All fields are optional and nullable.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[datetime] = None

    model_config = {"extra": "forbid"}  # No extra fields allowed


class UserListQuery(BaseModel):
    """
    Schema for query parameters to filter and paginate users.
    """

    limit: int = 10
    offset: int = 0
    email: Optional[str] = None
    is_active: Optional[bool] = None
    sort: str = "created_at:desc"

    model_config = {"extra": "forbid"}

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Method to validate limit"""
        if v < 1 or v > 100:
            raise ValueError("limit must be between 1 and 100")
        return v

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, v: str) -> str:
        """Method to valide the sort"""
        field, direction = v.split(":") if ":" in v else (v, "asc")
        if field not in ["email", "created_at", "updated_at"]:
            raise ValueError(f"Invalid sort field: {field}")
        if direction not in ["asc", "desc"]:
            raise ValueError(f"Invalid sort direction: {direction}")
        return v


class UserListResponse(BaseModel):
    """
    Schema for paginated user list response.
    """

    users: List[UserResponse]
    meta: dict

    model_config = {"from_attributes": True}


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
