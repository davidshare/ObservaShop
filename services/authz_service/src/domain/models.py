from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = {"schema": "authz"}

    id: int = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, nullable=False)
    description: Optional[str] = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user_roles: List["UserRole"] = Relationship(back_populates="role")
    role_permissions: List["RolePermission"] = Relationship(back_populates="role")


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    __table_args__ = {"schema": "authz"}

    user_id: UUID = Field(primary_key=True)
    role_id: int = Field(primary_key=True, foreign_key="authz.roles.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    role: Role = Relationship(back_populates="user_roles")


class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "authz"}

    id: int = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, nullable=False)
    description: Optional[str] = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    role_permissions: List["RolePermission"] = Relationship(back_populates="permission")


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": "authz"}

    role_id: int = Field(primary_key=True, foreign_key="authz.roles.id")
    permission_id: int = Field(primary_key=True, foreign_key="authz.permissions.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    role: Role = Relationship(back_populates="role_permissions")
    permission: Permission = Relationship(back_populates="role_permissions")
