from typing import List
from uuid import UUID

from pydantic import BaseModel


class AuthZCheckRequest(BaseModel):
    """
    Request schema for authorization check.
    """

    user_id: UUID
    action: str
    resource: str

    model_config = {"extra": "forbid"}  # No extra fields allowed


class AuthZCheckResponse(BaseModel):
    """
    Response schema for authorization check.
    """

    allowed: bool
    missing_permissions: List[str] = []
