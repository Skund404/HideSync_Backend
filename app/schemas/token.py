# File: app/schemas/token.py
"""
Authentication token schemas for the HideSync API.

This module contains Pydantic models for token-based authentication,
including access tokens and token payloads.
"""

from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    """
    Schema for access token response.

    Contains the token value and type for OAuth2-compatible responses.
    """
    access_token: str = ...
    token_type: str = ...


class TokenPayload(BaseModel):
    """
    Schema for the contents of JWT token payload.

    Contains user identifiers and other token-specific data.
    """
    sub: Optional[int] = None
    exp: Optional[int] = None