# app/repositories/password_reset_repository.py
"""
Repository implementation for password reset tokens in HideSync.

This module provides data access for password reset tokens via the repository pattern.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.repositories.base_repository import BaseRepository
from app.db.models.password_reset import PasswordResetToken


class PasswordResetRepository(BaseRepository[PasswordResetToken]):
    """Repository for password reset token entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PasswordResetRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = PasswordResetToken

    def create_for_user(
        self, user_id: int, expiration_hours: int = 24
    ) -> PasswordResetToken:
        """
        Create a new password reset token for a user.

        Args:
            user_id: User ID
            expiration_hours: Hours until token expiration

        Returns:
            Created token
        """
        token = PasswordResetToken.create_token(user_id, expiration_hours)
        self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def get_by_token(self, token: str) -> Optional[PasswordResetToken]:
        """
        Get a password reset token by its value.

        Args:
            token: Token string

        Returns:
            Token entity if found, None otherwise
        """
        return self.session.query(self.model).filter(self.model.token == token).first()

    def get_valid_token_for_user(self, user_id: int) -> Optional[PasswordResetToken]:
        """
        Get a valid (not expired, not used) token for a user.

        Args:
            user_id: User ID

        Returns:
            Valid token if found, None otherwise
        """
        return (
            self.session.query(self.model)
            .filter(
                self.model.user_id == user_id,
                self.model.used == False,
                self.model.expires_at > datetime.utcnow(),
            )
            .first()
        )

    def invalidate_all_for_user(self, user_id: int) -> bool:
        """
        Invalidate all tokens for a user.

        Args:
            user_id: User ID

        Returns:
            True if tokens were invalidated
        """
        try:
            self.session.query(self.model).filter(self.model.user_id == user_id).update(
                {"used": True}
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def mark_used(self, token_id: int) -> bool:
        """
        Mark a token as used.

        Args:
            token_id: Token ID

        Returns:
            True if token was marked as used
        """
        try:
            self.session.query(self.model).filter(self.model.id == token_id).update(
                {"used": True}
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False
