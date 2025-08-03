from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class RoleCreate(BaseModel):
    """
    Schema for creating a new role.
    """

    name: str
    description: Optional[str] = None

    model_config = {"extra": "forbid"}


class RoleUpdate(BaseModel):
    """
    Schema for updating an existing role.
    All fields are optional.
    """

    name: Optional[str] = None
    description: Optional[str] = None

    model_config = {"extra": "forbid"}


class RoleResponse(BaseModel):
    """
    Schema for returning role data.
    Excludes junction tables.
    """

    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    """
    Schema for paginated role list response.
    """

    roles: List[RoleResponse]
    meta: dict

    model_config = {"from_attributes": True}


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


class UserRoleCreate(BaseModel):
    """
    Schema for assigning a role to a user.
    """

    user_id: UUID
    role_id: UUID

    model_config = {"extra": "forbid"}


class UserRoleResponse(BaseModel):
    """
    Schema for returning user-role assignment.
    """

    user_id: UUID
    role_id: UUID
    assigned_at: datetime

    model_config = {"from_attributes": True}


class UserRoleListResponse(BaseModel):
    """
    Schema for paginated user-role list response.
    """

    roles: List[UserRoleResponse]
    meta: dict

    model_config = {"from_attributes": True}


class PermissionCreate(BaseModel):
    """
    Schema for creating a new permission.
    """

    name: str
    description: Optional[str] = None

    model_config = {"extra": "forbid"}


class PermissionUpdate(BaseModel):
    """
    Schema for updating an existing permission.
    All fields are optional.
    """

    name: Optional[str] = None
    description: Optional[str] = None

    model_config = {"extra": "forbid"}


class PermissionResponse(BaseModel):
    """
    Schema for returning permission data.
    """

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PermissionListResponse(BaseModel):
    """
    Schema for paginated permission list response.
    """

    permissions: List[PermissionResponse]
    meta: dict

    model_config = {"from_attributes": True}
