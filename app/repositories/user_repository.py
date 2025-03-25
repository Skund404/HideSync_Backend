# app/repositories/user_repository.py
"""
Repository implementation for users in HideSync.

This module provides data access for users via the repository pattern.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.repositories.base_repository import BaseRepository
from app.db.models.user import User


class UserRepository(BaseRepository[User]):
    """Repository for user entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the UserRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = User

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address.

        Args:
            email: Email address to search for

        Returns:
            User if found, None otherwise
        """
        return self.session.query(self.model).filter(self.model.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.

        Args:
            username: Username to search for

        Returns:
            User if found, None otherwise
        """
        return (
            self.session.query(self.model)
            .filter(self.model.username == username)
            .first()
        )

    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[User]:
        """
        List users with filters.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria (is_active, is_superuser, etc.)

        Returns:
            List of matching users
        """
        query = self.session.query(self.model)

        # Apply standard filters
        for key, value in filters.items():
            if hasattr(self.model, key) and key not in ["search", "email", "role_id"]:
                query = query.filter(getattr(self.model, key) == value)

        # Search filter
        if "search" in filters and filters["search"]:
            search = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    self.model.full_name.ilike(search),
                    self.model.email.ilike(search),
                    self.model.username.ilike(search),
                )
            )

        # Email filter with partial match
        if "email" in filters and filters["email"]:
            query = query.filter(self.model.email.ilike(f"%{filters['email']}%"))

        # Role filter
        if "role_id" in filters and filters["role_id"]:
            # This requires the user_role association table to be imported
            from app.db.models.role import user_role

            query = query.join(user_role, user_role.c.user_id == self.model.id).filter(
                user_role.c.role_id == filters["role_id"]
            )

        # Apply pagination and ordering
        query = query.order_by(self.model.id)
        query = query.offset(skip).limit(limit)

        return query.all()
