# File: app/schemas/user.py
"""
User schemas for the HideSync API.

This module contains Pydantic models for user management,
including user creation, update, and authentication.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """
    Base schema with common user fields.
    """
    email: EmailStr = Field(..., description="Email address")
    username: str = Field(..., description="Username")
    is_active: Optional[bool] = Field(True, description="Whether the user is active")
    full_name: Optional[str] = Field(None, description="Full name")
    is_superuser: Optional[bool] = Field(False, description="Whether the user is a superuser")


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    """
    password: str = Field(..., description="Password")

    @validator('password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v

    @validator('username')
    def username_format(cls, v):
        """Validate username format."""
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        return v


class UserUpdate(BaseModel):
    """
    Schema for updating user information.

    All fields are optional to allow partial updates.
    """
    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")
    password: Optional[str] = Field(None, description="Password")

    @validator('password')
    def password_strength(cls, v):
        """Validate password strength if provided."""
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
            if not any(char.isdigit() for char in v):
                raise ValueError('Password must contain at least one digit')
            if not any(char.isalpha() for char in v):
                raise ValueError('Password must contain at least one letter')
        return v


class User(UserBase):
    """
    Schema for user information.
    """
    id: int = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Timestamp when the user was created")

    class Config:
        from_attributes = True


class UserWithPermissions(User):
    """
    Schema for user information with permissions.
    """
    permissions: List[str] = Field([], description="User permissions")
    roles: List[str] = Field([], description="User roles")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        from_attributes = True


class PasswordReset(BaseModel):
    """
    Schema for password reset request.
    """
    email: EmailStr = Field(..., description="Email address for account to reset")


class PasswordChange(BaseModel):
    """
    Schema for password change request.
    """
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")

    @validator('new_password')
    def password_strength(cls, v, values):
        """Validate password strength and ensure it's different from current."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from the current password')
        return v