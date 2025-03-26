# app/repositories/role_repository.py
"""
Repository implementation for roles in HideSync.

This module provides data access for roles via the repository pattern.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.repositories.base_repository import BaseRepository
from app.db.models.role import Role, Permission, user_role, role_permission


class RoleRepository(BaseRepository[Role]):
    """Repository for role entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RoleRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Role

    def get_by_name(self, name: str) -> Optional[Role]:
        """
        Get a role by name.

        Args:
            name: Role name

        Returns:
            Role if found, None otherwise
        """
        return self.session.query(self.model).filter(self.model.name == name).first()

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[Role]:
        """
        List roles with filters.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria

        Returns:
            List of matching roles
        """
        query = self.session.query(self.model)

        # Apply standard filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Search filter
        if "search" in filters and filters["search"]:
            search = f"%{filters['search']}%"
            query = query.filter(
                or_(self.model.name.ilike(search), self.model.description.ilike(search))
            )

        # Apply pagination and ordering
        query = query.order_by(self.model.name)
        query = query.offset(skip).limit(limit)

        return query.all()

    def get_user_roles(self, user_id: int) -> List[Role]:
        """
        Get roles assigned to a user.

        Args:
            user_id: User ID

        Returns:
            List of roles assigned to the user
        """
        return (
            self.session.query(self.model)
            .join(user_role, user_role.c.role_id == self.model.id)
            .filter(user_role.c.user_id == user_id)
            .all()
        )

    def assign_role_to_user(self, user_id: int, role_id: int) -> bool:
        """
        Assign a role to a user.

        Args:
            user_id: User ID
            role_id: Role ID

        Returns:
            True if assignment was successful
        """
        # Check if assignment already exists
        existing = (
            self.session.query(user_role)
            .filter_by(user_id=user_id, role_id=role_id)
            .first()
        )

        if existing:
            return True

        # Create new assignment
        try:
            self.session.execute(
                user_role.insert().values(user_id=user_id, role_id=role_id)
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def remove_role_from_user(self, user_id: int, role_id: int) -> bool:
        """
        Remove a role from a user.

        Args:
            user_id: User ID
            role_id: Role ID

        Returns:
            True if removal was successful
        """
        try:
            self.session.execute(
                user_role.delete().where(
                    (user_role.c.user_id == user_id) & (user_role.c.role_id == role_id)
                )
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def assign_permissions(self, role_id: int, permission_ids: List[int]) -> bool:
        """
        Assign permissions to a role.

        Args:
            role_id: Role ID
            permission_ids: List of permission IDs

        Returns:
            True if assignment was successful
        """
        try:
            # First, remove existing assignments
            self.session.execute(
                role_permission.delete().where(role_permission.c.role_id == role_id)
            )

            # Then add new assignments
            for permission_id in permission_ids:
                self.session.execute(
                    role_permission.insert().values(
                        role_id=role_id, permission_id=permission_id
                    )
                )

            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False


class PermissionRepository(BaseRepository[Permission]):
    """Repository for permission entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PermissionRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Permission

    def get_by_code(self, code: str) -> Optional[Permission]:
        """
        Get a permission by code.

        Args:
            code: Permission code

        Returns:
            Permission if found, None otherwise
        """
        return self.session.query(self.model).filter(self.model.code == code).first()

    def get_by_codes(self, codes: List[str]) -> List[Permission]:
        """
        Get permissions by their codes.

        Args:
            codes: List of permission codes

        Returns:
            List of matching permissions
        """
        return self.session.query(self.model).filter(self.model.code.in_(codes)).all()

    def get_by_resource(self, resource: str) -> List[Permission]:
        """
        Get permissions for a resource.

        Args:
            resource: Resource name

        Returns:
            List of permissions for the resource
        """
        return (
            self.session.query(self.model).filter(self.model.resource == resource).all()
        )

    def get_role_permissions(self, role_id: int) -> List[Permission]:
        """
        Get permissions assigned to a role.

        Args:
            role_id: Role ID

        Returns:
            List of permissions assigned to the role
        """
        return (
            self.session.query(self.model)
            .join(role_permission, role_permission.c.permission_id == self.model.id)
            .filter(role_permission.c.role_id == role_id)
            .all()
        )
