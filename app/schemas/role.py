# app/schemas/role.py
"""
Role schemas for the HideSync API.

This module contains Pydantic models for role-based access control,
including role creation, updating, and permission assignment.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class PermissionBase(BaseModel):
    """Base schema for permission data."""

    code: str = Field(..., description="Unique permission code")
    name: str = Field(..., description="Permission display name")
    description: Optional[str] = Field(None, description="Permission description")
    resource: str = Field(..., description="Resource this permission applies to")


class Permission(PermissionBase):
    """Schema for permission information."""

    id: int = Field(..., description="Permission ID")

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    """Base schema for role data."""

    name: str = Field(..., description="Role name", min_length=2, max_length=50)
    description: Optional[str] = Field(None, description="Role description")
    is_system_role: bool = Field(
        False, description="Whether this is a system-defined role"
    )


class RoleCreate(RoleBase):
    """Schema for creating a new role."""

    permission_codes: List[str] = Field(
        [], description="Codes of permissions to assign"
    )

    @validator("name")
    def name_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Role name cannot be empty")
        return v


class RoleUpdate(BaseModel):
    """Schema for updating role information."""

    name: Optional[str] = Field(
        None, description="Role name", min_length=2, max_length=50
    )
    description: Optional[str] = Field(None, description="Role description")
    permission_codes: Optional[List[str]] = Field(
        None, description="Codes of permissions to assign"
    )

    @validator("name")
    def name_must_be_valid(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Role name cannot be empty")
        return v


class Role(RoleBase):
    """Schema for role information."""

    id: int = Field(..., description="Role ID")
    created_at: datetime = Field(..., description="When the role was created")
    updated_at: datetime = Field(..., description="When the role was last updated")
    permissions: List[Permission] = Field(
        [], description="Permissions assigned to this role"
    )

    class Config:
        from_attributes = True


class RoleAssignmentBase(BaseModel):
    """Base schema for role assignment data."""

    user_id: int = Field(..., description="User ID")
    role_id: int = Field(..., description="Role ID")


class RoleAssignmentCreate(RoleAssignmentBase):
    """Schema for creating a new role assignment."""

    pass


class RoleAssignment(RoleAssignmentBase):
    """Schema for role assignment information."""

    id: int = Field(..., description="Role assignment ID")
    created_at: datetime = Field(..., description="When the assignment was created")

    class Config:
        from_attributes = True
