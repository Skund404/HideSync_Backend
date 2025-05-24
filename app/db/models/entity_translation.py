# File: app/db/models/entity_translation.py

"""
Entity Translation Model for Universal Localization System

This model provides translation capabilities for all entity types in the HideSync system,
following the exact same pattern as the EnumTranslation model in the Dynamic Enum System.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.models.base import Base


class EntityTranslation(Base):
    """
    Universal translation model for all entity fields.

    This table stores translations for any entity type (workflows, products, tools, etc.)
    in a single, normalized structure. It mirrors the pattern used by EnumTranslation
    in the Dynamic Enum System for consistency.

    Attributes:
        id: Primary key for the translation record
        entity_type: Type of entity being translated (e.g., 'workflow', 'product')
        entity_id: ID of the specific entity instance
        locale: Language code (e.g., 'en', 'de', 'fr-CA')
        field_name: Name of the field being translated (e.g., 'name', 'description')
        translated_value: The actual translated content
        created_at: Timestamp when translation was created
        updated_at: Timestamp when translation was last modified
    """
    __tablename__ = "entity_translations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="Primary key for translation record"
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of entity being translated (e.g., 'workflow', 'product')"
    )

    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="ID of the specific entity instance"
    )

    locale: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Language code (e.g., 'en', 'de', 'fr-CA')"
    )

    field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Name of the field being translated (e.g., 'name', 'description')"
    )

    translated_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The actual translated content"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when translation was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when translation was last modified"
    )

    __table_args__ = (
        # Optimized index for the most common lookup pattern
        Index(
            'idx_entity_translation_lookup',
            'entity_type', 'entity_id', 'locale', 'field_name',
            comment="Primary lookup index for translation retrieval"
        ),

        # Ensure unique translations per entity/locale/field combination
        UniqueConstraint(
            'entity_type', 'entity_id', 'locale', 'field_name',
            name='uq_entity_translation',
            comment="Ensures unique translation per entity/locale/field"
        ),

        # Additional indexes for common query patterns
        Index(
            'idx_entity_translation_entity_type',
            'entity_type',
            comment="Index for queries by entity type"
        ),

        Index(
            'idx_entity_translation_locale',
            'locale',
            comment="Index for queries by locale"
        ),

        # Table-level comment
        {'comment': 'Universal translation storage for all entity types in HideSync'}
    )

    def __repr__(self) -> str:
        """String representation for debugging and logging."""
        return (
            f"<EntityTranslation("
            f"id={self.id}, "
            f"entity_type='{self.entity_type}', "
            f"entity_id={self.entity_id}, "
            f"locale='{self.locale}', "
            f"field_name='{self.field_name}', "
            f"value_length={len(self.translated_value)}"
            f")>"
        )

    def to_dict(self) -> dict:
        """Convert translation to dictionary for API responses."""
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'locale': self.locale,
            'field_name': self.field_name,
            'translated_value': self.translated_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }