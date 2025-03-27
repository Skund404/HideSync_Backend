# File: app/db/models/documentation.py
"""
Documentation models for the HideSync system.

This module defines the models for the documentation system, including categories,
resources, contextual help mappings, and application contexts. These models support
a knowledge base for users with hierarchical organization and contextual help.
"""

import uuid
from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Integer,
    ForeignKey,
    JSON,
    DateTime,
    Boolean,
    Table,
    Float,
    UniqueConstraint,
)

# Assuming Mapped and mapped_column are needed if using newer SQLAlchemy syntax
# If not, remove these imports.
from sqlalchemy.orm import relationship, validates, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import SkillLevel

# Association table for many-to-many relationship between resources and categories
documentation_category_assignment = Table(
    "documentation_category_assignments",
    AbstractBase.metadata,
    # *** FIXED: Add default UUID generator for the primary key ***
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column(
        "category_id",
        String(36),
        ForeignKey("documentation_categories.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "resource_id",
        String(36),
        ForeignKey("documentation_resources.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("display_order", Integer, default=0),
    Column("assigned_at", DateTime, default=datetime.utcnow),
    UniqueConstraint("category_id", "resource_id", name="uq_category_resource"),
)


class DocumentationType(str, PyEnum):
    """Enumeration of documentation resource types."""

    GUIDE = "GUIDE"
    TUTORIAL = "TUTORIAL"
    REFERENCE = "REFERENCE"
    FAQ = "FAQ"
    TROUBLESHOOTING = "TROUBLESHOOTING"


class DocumentationStatus(str, PyEnum):
    """Enumeration of documentation resource statuses."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DocumentationCategory(AbstractBase, ValidationMixin, TimestampMixin):
    """
    DocumentationCategory model for organizing documentation resources.

    This model defines categories for documentation, enabling organization
    of content into logical sections for easier navigation. Categories can
    be nested to create a hierarchy.
    """

    __tablename__ = "documentation_categories"
    __validated_fields__: ClassVar[Set[str]] = {"name", "slug"}

    # Basic information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(100))
    slug = Column(String(100), unique=True, nullable=False)
    display_order = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)

    # Organizational structure
    parent_category_id = Column(
        String(36), ForeignKey("documentation_categories.id"), nullable=True
    )

    # Timestamps are handled by TimestampMixin

    # Relationships
    parent = relationship(
        "DocumentationCategory",
        back_populates="subcategories",
        remote_side="DocumentationCategory.id",
        # *** FIXED: Use string for foreign_keys ***
        foreign_keys="DocumentationCategory.parent_category_id",
    )

    subcategories = relationship(
        "DocumentationCategory",
        back_populates="parent",
        # *** FIXED: Use string for foreign_keys ***
        foreign_keys="DocumentationCategory.parent_category_id",
    )

    resources = relationship(
        "DocumentationResource",
        secondary=documentation_category_assignment,
        back_populates="categories",
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate category name.

        Args:
            key: Field name ('name')
            name: Category name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Category name must be at least 2 characters")
        return name.strip()

    @validates("slug")
    def validate_slug(self, key: str, slug: str) -> str:
        """
        Validate category slug.

        Args:
            key: Field name ('slug')
            slug: Category slug to validate

        Returns:
            Validated slug

        Raises:
            ValueError: If slug is empty or contains invalid characters
        """
        if not slug or len(slug.strip()) < 2:
            raise ValueError("Category slug must be at least 2 characters")

        # Check for valid slug format (lowercase, hyphens, no spaces)
        import re

        if not re.match(r"^[a-z0-9-]+$", slug):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )

        return slug.strip()

    @hybrid_property
    def resource_count(self) -> int:
        """
        Count resources in this category.

        Returns:
            Number of resources in the category
        """
        # Ensure relationship is loaded or handle potential None
        return len(self.resources) if self.resources is not None else 0

    @hybrid_property
    def has_subcategories(self) -> bool:
        """
        Check if category has subcategories.

        Returns:
            True if category has subcategories, False otherwise
        """
        # Ensure relationship is loaded or handle potential None
        return len(self.subcategories) > 0 if self.subcategories is not None else False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DocumentationCategory instance to a dictionary.

        Returns:
            Dictionary representation of the documentation category
        """
        result = super().to_dict()

        # Add calculated properties
        result["resource_count"] = self.resource_count
        result["has_subcategories"] = self.has_subcategories

        return result

    def __repr__(self) -> str:
        """Return string representation of the DocumentationCategory."""
        return f"<DocumentationCategory(id='{self.id}', name='{self.name}')>"


class DocumentationResource(AbstractBase, ValidationMixin, TimestampMixin):
    """
    DocumentationResource model for storing documentation content.

    This model represents individual documentation resources, such as guides,
    tutorials, and reference documentation, with content and metadata.
    """

    __tablename__ = "documentation_resources"
    __validated_fields__: ClassVar[Set[str]] = {"title", "content"}

    # Basic information
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)

    # Categorization
    type = Column(Enum(DocumentationType), nullable=False)
    skill_level = Column(Enum(SkillLevel))
    version = Column(String(20))
    tags = Column(JSON, nullable=True)
    related_resource_ids = Column(JSON, nullable=True)  # List of resource IDs

    # Author and timestamps
    # Assuming author_id links to a User model's ID (adjust ForeignKey if needed)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Publication info
    is_public = Column(Boolean, default=True)
    thumbnail_url = Column(String(255))
    media_attachments = Column(
        JSON, nullable=True
    )  # JSON object for videos, images, etc.
    status = Column(Enum(DocumentationStatus), default=DocumentationStatus.PUBLISHED)

    # Relationships
    categories = relationship(
        "DocumentationCategory",
        secondary=documentation_category_assignment,
        back_populates="resources",
    )

    contextual_help_mappings = relationship(
        "ContextualHelpMapping", back_populates="resource", cascade="all, delete-orphan"
    )

    # Optional: Relationship to User model if you want to access the author object
    # author = relationship("User", back_populates="documentation_resources")

    @validates("title")
    def validate_title(self, key: str, title: str) -> str:
        """
        Validate resource title.

        Args:
            key: Field name ('title')
            title: Resource title to validate

        Returns:
            Validated title

        Raises:
            ValueError: If title is empty or too short
        """
        if not title or len(title.strip()) < 3:
            raise ValueError("Resource title must be at least 3 characters")
        return title.strip()

    @validates("content")
    def validate_content(self, key: str, content: str) -> str:
        """
        Validate resource content.

        Args:
            key: Field name ('content')
            content: Resource content to validate

        Returns:
            Validated content

        Raises:
            ValueError: If content is empty or too short
        """
        if not content or len(content.strip()) < 10:
            raise ValueError("Resource content must be at least 10 characters")
        return content

    @hybrid_property
    def word_count(self) -> int:
        """
        Count words in content.

        Returns:
            Number of words in content
        """
        if not self.content:
            return 0
        return len(self.content.split())

    @hybrid_property
    def reading_time_minutes(self) -> int:
        """
        Estimate reading time in minutes.

        Uses average reading speed of 200 words per minute.

        Returns:
            Estimated reading time in minutes
        """
        return max(1, self.word_count // 200)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DocumentationResource instance to a dictionary.

        Returns:
            Dictionary representation of the documentation resource
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.type:
            result["type"] = self.type.value

        if self.status:
            result["status"] = self.status.value

        if self.skill_level:
            result["skill_level"] = self.skill_level.name

        # Handle JSON fields (ensure they are lists/dicts, not strings)
        for field in ["tags", "related_resource_ids", "media_attachments"]:
            value = getattr(self, field, None)
            if isinstance(value, str):
                import json

                try:
                    result[field] = json.loads(value)
                except json.JSONDecodeError:
                    # Handle potential invalid JSON string, default to empty list/dict
                    result[field] = [] if field != "media_attachments" else {}
            elif value is None:
                result[field] = [] if field != "media_attachments" else {}
            else:
                result[field] = value  # Already a list/dict

        # Add calculated properties
        result["word_count"] = self.word_count
        result["reading_time_minutes"] = self.reading_time_minutes

        return result

    def __repr__(self) -> str:
        """Return string representation of the DocumentationResource."""
        return f"<DocumentationResource(id='{self.id}', title='{self.title}', type='{self.type}')>"


class ApplicationContext(AbstractBase, ValidationMixin, TimestampMixin):
    """
    ApplicationContext model for tracking UI contexts that can have associated help.

    This model represents specific parts of the application's UI that might
    need contextual help, such as specific pages, forms, or features.
    """

    __tablename__ = "application_contexts"
    __validated_fields__: ClassVar[Set[str]] = {"context_key", "name"}

    # Basic information
    context_key = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Navigation/routing information
    route = Column(String(200))
    component_path = Column(String(200))

    # Relationships
    contextual_help_mappings = relationship(
        "ContextualHelpMapping",
        back_populates="application_context",
        cascade="all, delete-orphan",
    )

    @validates("context_key")
    def validate_context_key(self, key: str, context_key: str) -> str:
        """
        Validate context key.

        Args:
            key: Field name ('context_key')
            context_key: The context key to validate

        Returns:
            Validated context key

        Raises:
            ValueError: If context key is invalid
        """
        if not context_key or len(context_key.strip()) < 2:
            raise ValueError("Context key must be at least 2 characters")

        # Check for valid key format (dots for namespacing)
        import re

        if not re.match(r"^[a-z0-9_.-]+$", context_key):
            raise ValueError(
                "Context key must contain only lowercase letters, numbers, dots, underscores, and hyphens"
            )

        return context_key.strip()

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate context name.

        Args:
            key: Field name ('name')
            name: The context name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is invalid
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Context name must be at least 2 characters")
        return name.strip()

    def __repr__(self) -> str:
        """Return string representation of the ApplicationContext."""
        return f"<ApplicationContext(id='{self.id}', key='{self.context_key}', name='{self.name}')>"


class ContextualHelpMapping(AbstractBase, ValidationMixin, TimestampMixin):
    """
    ContextualHelpMapping model for connecting resources to application contexts.

    This model creates the relationship between documentation resources and
    application UI contexts, enabling the display of relevant help content
    based on where the user is in the application.
    """

    __tablename__ = "contextual_help_mappings"
    __validated_fields__: ClassVar[Set[str]] = {"resource_id", "context_key"}

    # Relationship keys
    resource_id = Column(
        String(36),
        ForeignKey("documentation_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    context_key = Column(
        String(100),
        ForeignKey("application_contexts.context_key", ondelete="CASCADE"),
        nullable=False,
    )

    # Metadata
    relevance_score = Column(Integer, default=50)  # 1-100 score for sorting results
    is_active = Column(Boolean, default=True)

    # Relationships
    resource = relationship(
        "DocumentationResource", back_populates="contextual_help_mappings"
    )
    application_context = relationship(
        "ApplicationContext", back_populates="contextual_help_mappings"
    )

    # Ensure uniqueness of resource-context pairs
    __table_args__ = (
        UniqueConstraint("resource_id", "context_key", name="uq_resource_context"),
    )

    @validates("relevance_score")
    def validate_relevance_score(self, key: str, score: int) -> int:
        """
        Validate relevance score.

        Args:
            key: Field name ('relevance_score')
            score: Score to validate

        Returns:
            Validated score

        Raises:
            ValueError: If score is outside valid range
        """
        if not isinstance(score, int):
            raise ValueError("Relevance score must be an integer")
        if score < 1 or score > 100:
            raise ValueError("Relevance score must be between 1 and 100")
        return score

    def __repr__(self) -> str:
        """Return string representation of the ContextualHelpMapping."""
        return f"<ContextualHelpMapping(id='{self.id}', resource_id='{self.resource_id}', context_key='{self.context_key}')>"
