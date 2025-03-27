# File: app/db/models/role.py
"""
Database models for role-based access control in HideSync.

This module defines SQLAlchemy models for roles, permissions,
and user-role assignments.
"""

# Keep necessary imports, remove Table, DateTime, datetime
from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.orm import relationship

from app.db.models.base import Base, TimestampMixin

# --- Import association tables from the new file ---
from app.db.models.associations import role_permission, user_role


# --- Remove the table definitions from here ---
# role_permission = Table(...)
# user_role = Table(...)


class Permission(Base):
    """
    Model for permissions.

    Represents a specific action that can be performed on a resource.
    """

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(200), nullable=True)
    resource = Column(String(50), nullable=False)

    # Relationships - Use imported table
    roles = relationship(
        "Role", secondary=role_permission, back_populates="permissions"
    )


class Role(Base, TimestampMixin):
    """
    Model for roles.

    Represents a collection of permissions that can be assigned to users.
    """

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(200), nullable=True)
    is_system_role = Column(Boolean, default=False, nullable=False)

    # Relationships - Use imported tables
    permissions = relationship(
        "Permission", secondary=role_permission, back_populates="roles"
    )
    users = relationship("User", secondary=user_role, back_populates="roles")


# Remove the comment block at the end if it's still there
