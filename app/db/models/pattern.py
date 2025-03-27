# File: app/db/models/pattern.py
"""
Pattern model for the Leathercraft ERP system.

This module defines the Pattern model representing design templates for
leatherworking projects. Patterns include design information, components,
and metadata for project creation.
"""

from typing import Dict, Any, ClassVar, Set
import json  # Import json for handling tags

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,  # Import Enum
    Integer,
    Boolean,
    JSON,
    Float,
)
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin

# Import the necessary Enums
from app.db.models.enums import ProjectType, SkillLevel, FileType  # <<< ADD FileType


class Pattern(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Pattern model representing design templates for projects.

    This model defines patterns/templates for leatherworking projects,
    including design information, components, and metadata.
    """

    __tablename__ = "patterns"
    __validated_fields__: ClassVar[Set[str]] = {"name", "file_path"}

    # Basic information
    name = Column(String(255), nullable=False, index=True)  # Added index=True
    description = Column(Text)
    skill_level = Column(Enum(SkillLevel), default=SkillLevel.BEGINNER)  # Added default

    # File information
    # --- CHANGE HERE: Use the new FileType Enum ---
    file_type = Column(Enum(FileType), default=FileType.PDF)
    # --- End Change ---
    file_path = Column(
        String(512), nullable=False
    )  # Increased length, made non-nullable
    thumbnail = Column(String(512))  # Increased length

    # Categorization
    tags = Column(JSON, nullable=True)  # Use JSON type if supported
    is_favorite = Column(Boolean, default=False)
    project_type = Column(
        Enum(ProjectType), nullable=True
    )  # Allow null if not always applicable

    # Metadata
    estimated_time = Column(
        Float
    )  # Changed to Float for more precision (e.g., 1.5 hours)
    estimated_difficulty = Column(Integer)  # 1-10 scale (or 1-5?)
    author_name = Column(String(100))
    is_public = Column(Boolean, default=False)
    version = Column(String(20))
    notes = Column(Text)  # Added notes field

    # Relationships
    components = relationship(
        "Component", back_populates="pattern", cascade="all, delete-orphan"
    )
    products = relationship("Product", back_populates="pattern")
    sale_items = relationship("SaleItem", back_populates="pattern")
    # project_templates relationship might be defined on ProjectTemplate model

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Validate pattern name."""
        if not name or len(name.strip()) < 3:
            raise ValueError("Pattern name must be at least 3 characters")
        return name.strip()

    @validates("file_path")
    def validate_file_path(self, key: str, path: str) -> str:
        """Validate file path."""
        # Basic validation, could add checks for format or existence if needed
        if not path or not path.strip():
            raise ValueError("File path is required")
        return path.strip()

    @validates("estimated_difficulty")
    def validate_difficulty(self, key: str, difficulty: int) -> int:
        """Validate difficulty rating (assuming 1-5 or 1-10)."""
        # Adjust range as needed (e.g., 1-5)
        if difficulty is not None and (difficulty < 1 or difficulty > 5):
            raise ValueError("Difficulty rating must be between 1 and 5")
        return difficulty

    @validates("estimated_time")
    def validate_estimated_time(self, key: str, time: float) -> float:
        """Validate estimated time."""
        if time is not None and time < 0:
            raise ValueError("Estimated time cannot be negative")
        return time

    def to_dict(self) -> Dict[str, Any]:
        """Convert Pattern instance to a dictionary."""
        # Assuming AbstractBase or TimestampMixin provides a base to_dict()
        result = super().to_dict() if hasattr(super(), "to_dict") else {}

        # Manually add fields if base to_dict is missing or incomplete
        for field in [
            "id",
            "name",
            "description",
            "file_path",
            "thumbnail",
            "tags",
            "is_favorite",
            "estimated_time",
            "estimated_difficulty",
            "author_name",
            "is_public",
            "version",
            "notes",
            "created_at",
            "updated_at",  # From TimestampMixin
        ]:
            if field not in result and hasattr(self, field):
                value = getattr(self, field)
                # Handle datetime serialization if needed
                if isinstance(value, datetime):
                    result[field] = value.isoformat()
                else:
                    result[field] = value

        # Convert enum values to strings
        if self.skill_level:
            result["skill_level"] = self.skill_level.name
        if self.project_type:
            result["project_type"] = self.project_type.name
        # --- ADD FileType conversion ---
        if self.file_type:
            result["file_type"] = self.file_type.name
        # --- End Add ---

        # Ensure tags are represented as a list/object, not a JSON string
        # (SQLAlchemy might handle JSON type automatically depending on dialect)
        if "tags" in result and isinstance(result["tags"], str):
            try:
                result["tags"] = json.loads(result["tags"])
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON tags for Pattern ID {self.id}")
                result["tags"] = []  # Fallback to empty list

        # Add component count (optional)
        result["component_count"] = len(self.components) if self.components else 0

        return result

    def __repr__(self) -> str:
        """Return string representation of the Pattern."""
        return (
            f"<Pattern(id={getattr(self, 'id', None)}, name='{self.name}', "
            f"file_type={self.file_type.name if self.file_type else None})>"
        )
