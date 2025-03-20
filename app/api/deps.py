# File: app/api/deps.py

from typing import Generator, Optional

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
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user_service = UserService(db)
    user = user_service.get(id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
    user_service = UserService(SessionLocal())
    if not user_service.is_active(current_user):
        raise HTTPException(status_code=400, detail="Inactive user")

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
    user_service = UserService(SessionLocal())
    if not user_service.is_superuser(current_user):
        raise HTTPException(
            status_code=403, detail="The user doesn't have sufficient privileges"
        )

    return current_user
