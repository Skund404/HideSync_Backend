# app/schemas/token.py
"""
Authentication token schemas for the HideSync API.

This module contains Pydantic models for token-based authentication,
including access tokens and token payloads.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Token(BaseModel):
    """
    Schema for access token response.

    Contains the token value and type for OAuth2-compatible responses.
    """

    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


class TokenPayload(BaseModel):
    """
    Schema for the contents of JWT token payload.

    Contains user identifiers and other token-specific data.
    """

    sub: Optional[int] = None
    exp: Optional[int] = None


class TokenRefresh(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")