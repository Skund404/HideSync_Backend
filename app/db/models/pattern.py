# File: app/db/models/pattern.py
"""
Pattern model for the Leathercraft ERP system.

This module defines the Pattern model representing design templates for
leatherworking projects. Patterns include design information, components,
and metadata for project creation.
"""

from typing import Dict, Any, ClassVar, Set

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Integer,
    Boolean,
    JSON,
    Float,
)
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ProjectType, SkillLevel


class Pattern(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Pattern model representing design templates for projects.

    This model defines patterns/templates for leatherworking projects,
    including design information, components, and metadata.
    """

    __tablename__ = "patterns"
    __validated_fields__: ClassVar[Set[str]] = {"name", "file_path"}

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    skill_level = Column(Enum(SkillLevel))

    # File information
    file_type = Column(String(20))  # 'SVG', 'PDF', 'IMAGE'
    file_path = Column(String(255))
    thumbnail = Column(String(255))

    # Categorization
    tags = Column(JSON, nullable=True)
    is_favorite = Column(Boolean, default=False)
    project_type = Column(Enum(ProjectType))

    # Metadata
    estimated_time = Column(Integer)               # in hours
    estimated_difficulty = Column(Integer)           # 1-10 scale
    author_name = Column(String(100))
    is_public = Column(Boolean, default=False)
    version = Column(String(20))

    # Relationships
    components = relationship(
        "Component", back_populates="pattern", cascade="all, delete-orphan"
    )
    products = relationship("Product", back_populates="pattern")
    sale_items = relationship("SaleItem", back_populates="pattern")
    # Removed the project_templates and projects relationships here.
    # ProjectTemplate is defined unambiguously in app/db/models/project.py

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate pattern name.

        Raises:
            ValueError: If name is empty or too short.
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Pattern name must be at least 3 characters")
        return name.strip()

    @validates("file_path")
    def validate_file_path(self, key: str, path: str) -> str:
        """
        Validate file path.

        Raises:
            ValueError: If path is empty.
        """
        if not path:
            raise ValueError("File path is required")
        return path

    @validates("estimated_difficulty")
    def validate_difficulty(self, key: str, difficulty: int) -> int:
        """
        Validate difficulty rating.

        Raises:
            ValueError: If difficulty is not between 1 and 10.
        """
        if difficulty is not None and (difficulty < 1 or difficulty > 10):
            raise ValueError("Difficulty rating must be between 1 and 10")
        return difficulty

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Pattern instance to a dictionary.
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.skill_level:
            result["skill_level"] = self.skill_level.name
        if self.project_type:
            result["project_type"] = self.project_type.name

        # Handle JSON fields
        if isinstance(result.get("tags"), str):
            import json

            try:
                result["tags"] = json.loads(result["tags"])
            except Exception:
                result["tags"] = []

        # Add a component count (optional)
        result["component_count"] = len(self.components) if self.components else 0

        return result

    def __repr__(self) -> str:
        """
        Return string representation of the Pattern.
        """
        return (
            f"<Pattern(id={self.id}, name='{self.name}', "
            f"project_type={self.project_type})>"
        )
