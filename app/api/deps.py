"""
FastAPI dependencies for HideSync.

This module provides dependency functions for FastAPI routes.
"""

from typing import Generator, Optional, Any, Dict, List, Union
from datetime import datetime
from enum import Enum

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


# New functions for serialization

def serialize_model(model: Any) -> Dict[str, Any]:
    """
    Serialize a model object to a dict, handling enums and timestamps.

    Args:
        model: SQLAlchemy model instance

    Returns:
        Dict: Serialized model data
    """
    if hasattr(model, "__dict__"):
        result = {}
        for key, value in model.__dict__.items():
            if key.startswith("_"):
                continue

            # Convert enum values
            if isinstance(value, Enum):
                result[key] = value.value
            # Ensure timestamps exist
            elif key in ("created_at", "updated_at") and value is None:
                result[key] = datetime.utcnow()
            # Recursively serialize nested objects
            elif hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool)):
                result[key] = serialize_model(value)
            else:
                result[key] = value
        return result
    return model


def serialize_response(data: Any) -> Any:
    """
    Process API response data to handle enums and missing timestamps.

    Args:
        data: Response data to process

    Returns:
        Processed data with enum values and timestamps
    """
    if isinstance(data, list):
        return [serialize_response(item) for item in data]
    elif hasattr(data, "__dict__"):
        return serialize_model(data)
    elif isinstance(data, dict):
        return {k: serialize_response(v) for k, v in data.items()}
    elif isinstance(data, Enum):
        return data.value
    return data


def serialize_for_response(data: Any) -> Any:
    """
    Convert data to be suitable for FastAPI response validation.
    Handles enum values, timestamps, and nested structures.
    """
    # Handle lists
    if isinstance(data, list):
        return [serialize_for_response(item) for item in data]

    # Handle dictionaries
    if isinstance(data, dict):
        return {k: serialize_for_response(v) for k, v in data.items()}

    # Handle enum values
    if isinstance(data, Enum):
        return data.value

    # Handle tuples that might be enum values
    if isinstance(data, tuple) and len(data) == 1:
        value = data[0]
        if isinstance(value, str):
            return value

    # Return regular values unchanged
    return data

def process_response(depends_on: Any = None):
    """
    Dependency to process the response data before returning.

    Usage:
    @router.get("/", response_model=List[Material], dependencies=[Depends(process_response)])

    Args:
        depends_on: Optional dependency to ensure execution order

    Returns:
        None
    """
    # This is just a marker dependency
    # The actual processing happens in a middleware or response handler
    return None