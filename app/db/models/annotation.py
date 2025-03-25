# File: app/db/models/annotation.py
"""
Annotation database model for HideSync.

This module defines the SQLAlchemy ORM model for annotations,
including database schema, relationships, and methods.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, ARRAY
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
    visibility = Column(String(20), nullable=False, default="private",
                        comment="PRIVATE/TEAM/PUBLIC")
    tags = Column(ARRAY(String), nullable=True)

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