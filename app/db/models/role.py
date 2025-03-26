# app/db/models/role.py
"""
Database models for role-based access control in HideSync.

This module defines SQLAlchemy models for roles, permissions,
and user-role assignments.
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.models.base import Base, TimestampMixin

# Association table for role-permission many-to-many relationship
role_permission = Table(
    "role_permission",
    Base.metadata,
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Association table for user-role many-to-many relationship
user_role = Table(
    "user_role",
    Base.metadata,
    Column(
        "user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("created_at", DateTime, default=datetime.utcnow),
)


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

    # Relationships
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

    # Relationships
    permissions = relationship(
        "Permission", secondary=role_permission, back_populates="roles"
    )
    users = relationship("User", secondary=user_role, back_populates="roles")


# Update the User model in user.py to include the roles relationship
# This is a reference to what needs to be added to the existing User model
"""
# In app/db/models/user.py:
from app.db.models.role import user_role

class User(Base, AuditMixin, TimestampMixin):
    # ... existing fields ...

    # Add this relationship
    roles = relationship("Role", secondary=user_role, back_populates="users")
"""
