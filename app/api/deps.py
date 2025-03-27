"""
FastAPI dependencies for HideSync.

This module provides dependency functions for FastAPI routes.
"""

from typing import Generator, Optional
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import schemas
from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.user_service import UserService
from app.db.models.user import User

# OAuth2 token URL for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=settings.TOKEN_URL)


def get_db() -> Generator:
    """
    Get database session.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
        db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        db: Database session
        token: JWT token from authorization header

    Returns:
        User: Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Decode JWT token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)

        # Ensure the token hasn't expired
        if datetime.fromtimestamp(token_data.exp) < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Ensure we have a subject
        if not token_data.sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except (JWTError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database by ID
    user_service = UserService(db)
    user = user_service.get_by_id(token_data.sub)

    if not user:
        # Log the issue for debugging
        print(f"User with ID {token_data.sub} not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_active_user(
        current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify user is active.

    Args:
        current_user: Current authenticated user

    Returns:
        User: Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user


def get_current_active_superuser(
        current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify user has superuser permissions.

    Args:
        current_user: Current authenticated user

    Returns:
        User: Current active superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have sufficient privileges"
        )

    return current_user