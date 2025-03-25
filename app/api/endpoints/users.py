# app/api/endpoints/users.py
"""
User management API endpoints for HideSync.

This module provides endpoints for user management,
including listing, creating, updating, and deleting users.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_current_active_superuser
from app.db.session import get_db
from app.schemas.user import (
    User,
    UserCreate,
    UserUpdate,
    UserListParams,
)
from app.services.user_service import UserService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[User])
def list_users(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_superuser),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    params: UserListParams = Depends(),
) -> List[User]:
    """
    Retrieve users with optional filtering and pagination.

    This endpoint requires superuser privileges.
    """
    user_service = UserService(db)
    filters = params.dict(exclude_none=True)
    return user_service.list_users(skip=skip, limit=limit, **filters)


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get information about the current user.
    """
    return current_user


@router.put("/me", response_model=User)
def update_current_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Update information for the current user.
    """
    user_service = UserService(db)

    # Don't allow changing is_superuser status
    if hasattr(user_in, "is_superuser"):
        delattr(user_in, "is_superuser")

    try:
        return user_service.update_user(current_user.id, user_in)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{user_id}", response_model=User)
def get_user(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., ge=1, description="The ID of the user to retrieve"),
    current_user: Any = Depends(get_current_active_superuser),
) -> User:
    """
    Get detailed information about a specific user.

    This endpoint requires superuser privileges.
    """
    user_service = UserService(db)
    try:
        return user_service.get_user(user_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )


@router.put("/{user_id}", response_model=User)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., ge=1, description="The ID of the user to update"),
    user_in: UserUpdate,
    current_user: Any = Depends(get_current_active_superuser),
) -> User:
    """
    Update a user.

    This endpoint requires superuser privileges.
    """
    user_service = UserService(db)
    try:
        return user_service.update_user(user_id, user_in)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., ge=1, description="The ID of the user to delete"),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Delete a user.

    This endpoint requires superuser privileges.
    """
    # Prevent deleting yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own user account",
        )

    user_service = UserService(db)
    try:
        user_service.delete_user(user_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
