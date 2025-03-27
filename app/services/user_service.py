# app/services/user_service.py (updates)
"""
User service for HideSync.

This module provides functionality for user management,
authentication, and authorization.
"""
from app.core import security

# app/services/user_service.py
"""
User service for HideSync.

This module provides functionality for user management,
authentication, and authorization.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import secrets
from jose import jwt, JWTError
from pydantic import ValidationError

from app import schemas
from app.services.base_service import BaseService
from app.db.models.user import User
from app.db.models.password_reset import PasswordResetToken
from app.repositories.user_repository import UserRepository
from app.repositories.password_reset_repository import PasswordResetRepository
from app.core.exceptions import (
    EntityNotFoundException,
    AuthenticationException,
    BusinessRuleException,
)
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.config import settings

# Add these methods to the existing UserService class


class UserService(BaseService[User]):
    # Assume existing implementation...

    def __init__(
        self,
        session: Session,
        repository=None,
        password_reset_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        email_service=None,
    ):
        """Initialize with updated dependencies"""
        # Existing initialization...
        self.password_reset_repository = (
            password_reset_repository or PasswordResetRepository(session)
        )
        self.email_service = email_service

    def request_password_reset(self, email: str) -> bool:
        """
        Request a password reset for a user.

        Args:
            email: User email address

        Returns:
            True if request was processed (whether user exists or not)
        """
        # Find the user by email
        user = self.repository.get_by_email(email)

        # Don't reveal if user exists or not for security
        if not user:
            return True

        with self.transaction():
            # Invalidate any existing tokens
            self.password_reset_repository.invalidate_all_for_user(user.id)

            # Create a new reset token
            token = self.password_reset_repository.create_for_user(user.id)

            # Send email with reset link
            if self.email_service:
                reset_url = (
                    f"{settings.FRONTEND_URL}/reset-password?token={token.token}"
                )
                self.email_service.send_password_reset_email(
                    user.email, user.full_name, reset_url
                )

            return True

    def validate_reset_token(self, token_str: str) -> Optional[User]:
        """
        Validate a password reset token.

        Args:
            token_str: Password reset token string

        Returns:
            User if token is valid, None otherwise
        """
        # Find the token
        token = self.password_reset_repository.get_by_token(token_str)

        # Check if token exists and is valid
        if not token or not token.is_valid:
            return None

        # Get user
        user = self.repository.get_by_id(token.user_id)
        return user

    def reset_password(self, token_str: str, new_password: str) -> bool:
        """
        Reset a user's password using a token.

        Args:
            token_str: Password reset token string
            new_password: New password

        Returns:
            True if password was reset

        Raises:
            AuthenticationException: If token is invalid
            BusinessRuleException: If password doesn't meet requirements
        """
        with self.transaction():
            # Validate token
            token = self.password_reset_repository.get_by_token(token_str)
            if not token or not token.is_valid:
                raise AuthenticationException("Invalid or expired password reset token")

            # Validate password strength
            if len(new_password) < 8:
                raise BusinessRuleException(
                    "Password must be at least 8 characters long"
                )

            # Get user
            user = self.repository.get_by_id(token.user_id)
            if not user:
                raise EntityNotFoundException("User", token.user_id)

            # Update password
            hashed_password = get_password_hash(new_password)
            self.repository.update(user.id, {"hashed_password": hashed_password})

            # Mark token as used
            self.password_reset_repository.mark_used(token.id)

            return True

    def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> bool:
        """
        Change a user's password.

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            True if password was changed

        Raises:
            EntityNotFoundException: If user not found
            AuthenticationException: If current password is incorrect
            BusinessRuleException: If new password doesn't meet requirements
        """
        with self.transaction():
            # Get user
            user = self.repository.get_by_id(user_id)
            if not user:
                raise EntityNotFoundException("User", user_id)

            # Verify current password
            if not verify_password(current_password, user.hashed_password):
                raise AuthenticationException("Current password is incorrect")

            # Validate new password
            if len(new_password) < 8:
                raise BusinessRuleException(
                    "Password must be at least 8 characters long"
                )

            if current_password == new_password:
                raise BusinessRuleException(
                    "New password must be different from current password"
                )

            # Update password
            hashed_password = get_password_hash(new_password)
            self.repository.update(user_id, {"hashed_password": hashed_password})

            return True

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            Dict with new access token and refresh token

        Raises:
            AuthenticationException: If refresh token is invalid
        """
        # Verify refresh token
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            token_data = schemas.TokenPayload(**payload)
        except (jwt.JWTError, ValidationError):
            raise AuthenticationException("Invalid refresh token")

        # Get user
        user = self.repository.get_by_id(token_data.sub)
        if not user or not user.is_active:
            raise AuthenticationException("Invalid refresh token")

        # Create new tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        access_token = create_access_token(user.id, expires_delta=access_token_expires)
        new_refresh_token = create_refresh_token(
            user.id, expires_delta=refresh_token_expires
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    # Add this to app/services/user_service.py
    def get_by_id(self, user_id: str):
        """
        Get a user by ID.

        Args:
            user_id: User ID (string)

        Returns:
            User or None
        """
        try:
            # Convert string ID to integer if needed
            user_id_int = int(user_id)
            user = self.db.query(User).filter(User.id == user_id_int).first()
            return user
        except (ValueError, TypeError):
            # If conversion fails, log the error and return None
            print(f"Invalid user ID format: {user_id}")
            return None