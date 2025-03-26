# File: app/db/models/associations.py
"""
Association tables for many-to-many relationships in HideSync models.
"""

from sqlalchemy import Table, Column, Integer, ForeignKey, DateTime
from datetime import datetime

# Import Base from your base model definition
from app.db.models.base import Base

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

