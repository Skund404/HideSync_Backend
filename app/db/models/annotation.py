# File: app/db/models/annotation.py
"""
Annotation database model for HideSync.

This module defines the SQLAlchemy ORM model for annotations,
including database schema, relationships, and methods.
"""

# Import JSON type
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    JSON,  # <-- Import JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.models.base import Base, AuditMixin, TimestampMixin


class Annotation(Base, AuditMixin, TimestampMixin):
    """
    Annotation model for attaching notes, comments, or metadata to various entities.

    This model represents a user annotation attached to an entity
    in the HideSync system, like a pattern, project, material, or sale.
    """

    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    visibility = Column(
        String(20),
        nullable=False,
        default="private",
        comment="PRIVATE/TEAM/PUBLIC",
    )
    # Use JSON to store the list of tags in SQLite
    tags = Column(JSON, nullable=True)  # <-- Changed ARRAY(String) to JSON

    # User who created the annotation
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="annotations")

    # Indexes for efficient querying
    __table_args__ = (
        # Composite index for efficiently finding annotations for a specific entity
        Index("ix_annotations_entity", "entity_type", "entity_id"),
    )

    def __repr__(self):
        """String representation of the annotation."""
        return f"Annotation(id={self.id}, entity_type={self.entity_type}, entity_id={self.entity_id})"

# Make sure User model has the corresponding relationship if it doesn't
# In your User model (e.g., app/db/models/user.py):
# annotations = relationship("Annotation", back_populates="user", cascade="all, delete-orphan")
