# app/schemas/user.py
"""
User schemas for the HideSync API.

This module contains Pydantic models for user management,
including user creation, update, and authentication.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator


class UserPasswordReset(BaseModel):
    """Schema for password reset request."""

    email: EmailStr = Field(..., description="Email address for account to reset")


class UserPasswordResetConfirm(BaseModel):
    """Schema for confirming a password reset."""

    new_password: str = Field(..., description="New password", min_length=8)
    confirm_password: str = Field(..., description="Confirm new password")

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class UserPasswordChange(BaseModel):
    """Schema for changing a user's password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password", min_length=8)
    confirm_password: str = Field(..., description="Confirm new password")

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class UserListParams(BaseModel):
    """Query parameters for user listing."""

    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_superuser: Optional[bool] = Field(None, description="Filter by superuser status")
    email: Optional[str] = Field(None, description="Filter by email (partial match)")
    search: Optional[str] = Field(None, description="Search in name or email")
    role_id: Optional[int] = Field(None, description="Filter by role")


class User(BaseModel):
    """Schema for user information."""

    id: int
    email: EmailStr
    username: str
    is_active: bool
    full_name: Optional[str] = None
    is_superuser: bool
    created_at: datetime
    roles: List[Dict[str, Any]] = []  # Add this field

    class Config:
        from_attributes = True
