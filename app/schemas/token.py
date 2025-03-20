# File: app/schemas/token.py

from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    """
    Schema for authentication token response.
    """
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """
    Schema for JWT token payload.
    """
    sub: Optional[int] = None