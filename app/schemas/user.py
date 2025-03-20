# File: app/schemas/user.py

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator, constr


# Shared properties
class UserBase(BaseModel):
    """Base User schema with common attributes"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    is_active: Optional[bool] = True
    full_name: Optional[str] = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    """Schema for creating a new user"""
    email: EmailStr
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_superuser: bool = False

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v


# Properties to receive via API on update
class UserUpdate(UserBase):
    """Schema for updating an existing user"""
    password: Optional[str] = None
    is_superuser: Optional[bool] = None


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    """Base schema for users with DB fields"""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        orm_mode = True


# Properties to return to client
class User(UserInDBBase):
    """Schema for user data returned to clients"""
    is_superuser: bool


# Properties stored in DB
class UserInDB(UserInDBBase):
    """Schema for user data stored in the database"""
    hashed_password: str
    is_superuser: bool