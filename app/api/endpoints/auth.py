"""
Authentication API endpoints for HideSync.

This module provides endpoints for user authentication, token management,
and password reset functionality.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.core import security
from app.core.config import settings
from app.services.user_service import UserService
from app.db.models.user import User

router = APIRouter()


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(
    refresh_token_in: schemas.TokenRefresh = Body(...),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Refresh access token using a refresh token.
    """
    user_service = UserService(db)
    try:
        tokens = user_service.refresh_token(refresh_token_in.refresh_token)
        return tokens
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_password_request(
    reset_request: schemas.UserPasswordReset = Body(...),
    db: Session = Depends(deps.get_db),
) -> None:
    """
    Request a password reset for a user.

    This endpoint will send a password reset email if the user exists.
    For security reasons, it does not reveal whether the email exists or not.
    """
    user_service = UserService(db)
    user_service.request_password_reset(reset_request.email)
    # Function ends without returning a value


@router.post("/reset-password/{token}", response_model=schemas.User)
def reset_password(
    token: str,
    password_data: schemas.UserPasswordResetConfirm = Body(...),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Reset a user's password using a reset token.
    """
    user_service = UserService(db)

    # Validate passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    try:
        # Validate token and get user
        user = user_service.validate_reset_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token",
            )

        # Reset password
        user_service.reset_password(token, password_data.new_password)

        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def change_password(
    password_data: schemas.UserPasswordChange = Body(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> None:
    """
    Change current user's password.
    """
    user_service = UserService(db)

    # Validate passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    try:
        user_service.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password,
        )
        # Function ends without returning a value
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
