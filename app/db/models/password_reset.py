# app/db/models/password_reset.py
"""
Database model for password reset tokens in HideSync.

This module defines the SQLAlchemy model for password reset tokens.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import secrets

from app.db.models.base import Base


class PasswordResetToken(Base):
    """
    Model for password reset tokens.

    Stores tokens for password reset requests with expiration.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String(100), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User")

    @classmethod
    def create_token(cls, user_id, expiration_hours=24):
        """Create a new password reset token for a user."""
        return cls(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.utcnow() + timedelta(hours=expiration_hours),
        )

    @property
    def is_expired(self):
        """Check if the token is expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        """Check if the token is valid (not expired and not used)."""
        return not self.is_expired and not self.used
