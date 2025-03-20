# File: app/api/endpoints/auth.py

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.core import security
from app.core.config import settings
from app.services.user_service import UserService
from app.db.models.user import User

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
def login_access_token(
        db: Session = Depends(deps.get_db),
        form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # Create user service
    user_service = UserService(db)

    # Authenticate user
    user = user_service.authenticate(
        email=form_data.username,  # OAuth2 form uses 'username' field for email
        password=form_data.password
    )

    # Validate authentication result
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user_service.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/signup", response_model=schemas.User)
def create_user(
        *,
        db: Session = Depends(deps.get_db),
        user_in: schemas.UserCreate,
) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user_service = UserService(db)

    user = user_service.get_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )

    user = user_service.get_by_username(username=user_in.username)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this username already exists",
        )

    user = user_service.create_user(user_in)
    return user


@router.get("/me", response_model=schemas.User)
def get_current_user(
        current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get current user information.
    """
    return current_user