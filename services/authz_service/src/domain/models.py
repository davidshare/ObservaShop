from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field, Relationship, SQLModel


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = {"schema": "authz"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the role (UUID).",
    )
    name: str = Field(
        max_length=50,
        unique=True,
        nullable=False,
        description="Role name (e.g., 'admin'). Must be unique.",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
        description="Optional description of the role's purpose.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the role was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the role was last updated.",
    )

    # Relationships: Let SQLAlchemy infer the join from the foreign key
    user_roles: List["UserRole"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    role_permissions: List["RolePermission"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    __table_args__ = {"schema": "authz"}

    user_id: UUID = Field(
        primary_key=True, description="ID of the user (from auth-service)."
    )
    role_id: UUID = Field(
        primary_key=True,
        foreign_key="authz.roles.id",  # Explicit foreign key
        description="ID of the role (from authz.roles).",
    )
    assigned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the role was assigned to the user.",
    )

    # Relationships
    role: Role = Relationship(
        back_populates="user_roles",
        sa_relationship_kwargs={"foreign_keys": "[UserRole.role_id]"},
    )


# Permission and RolePermission models remain unchanged
class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "authz"}

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the permission (UUID).",
    )
    name: str = Field(
        max_length=100,
        unique=True,
        nullable=False,
        description="Permission name in 'resource:action' format (e.g., 'product:create').",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
        description="Optional description of what the permission allows.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the permission was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the permission was last updated.",
    )

    role_permissions: List["RolePermission"] = Relationship(
        back_populates="permission",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": "authz"}

    role_id: UUID = Field(
        primary_key=True,
        foreign_key="authz.roles.id",  # Explicit foreign key
        description="ID of the role (from authz.roles).",
    )
    permission_id: UUID = Field(
        primary_key=True,
        foreign_key="authz.permissions.id",  # Explicit foreign key
        description="ID of the permission (from authz.permissions).",
    )
    assigned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the permission was assigned to the role.",
    )

    role: Role = Relationship(
        back_populates="role_permissions",
        sa_relationship_kwargs={"foreign_keys": "[RolePermission.role_id]"},
    )
    permission: Permission = Relationship(
        back_populates="role_permissions",
        sa_relationship_kwargs={"foreign_keys": "[RolePermission.permission_id]"},
    )
