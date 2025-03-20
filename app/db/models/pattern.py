"""
Pattern model for the Leathercraft ERP system.

This module defines the Pattern model representing design templates for
leatherworking projects. Patterns include design information, components,
and metadata for project creation.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Integer,
    Boolean,
    JSON,
    ForeignKey,
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

    Attributes:
        name: Pattern name
        description: Pattern description
        skill_level: Required skill level
        file_type: Type of pattern file
        file_path: Path to pattern file
        thumbnail: Thumbnail image
        tags: Tags for categorization
        is_favorite: Whether this is a favorite pattern
        project_type: Type of project
        estimated_time: Estimated time to complete (hours)
        estimated_difficulty: Difficulty rating (1-10)
        author_name: Pattern creator
        is_public: Whether pattern is public
        version: Pattern version
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
    estimated_time = Column(Integer)  # in hours
    estimated_difficulty = Column(Integer)  # 1-10 scale
    author_name = Column(String(100))
    is_public = Column(Boolean, default=False)
    version = Column(String(20))

    # Relationships
    components = relationship(
        "Component", back_populates="pattern", cascade="all, delete-orphan"
    )
    products = relationship("Product", back_populates="pattern")
    sale_items = relationship("SaleItem", back_populates="pattern")

    # Updated relationships to resolve mapping issues
    project_templates = relationship(
        "ProjectTemplate",
        back_populates="pattern",
        cascade="all, delete-orphan",
        overlaps="projects",
    )

    # ViewOnly relationship to avoid conflicts
    projects = relationship("Project", secondary="project_templates", viewonly=True)

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate pattern name.

        Args:
            key: Field name ('name')
            name: Pattern name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Pattern name must be at least 3 characters")
        return name.strip()

    @validates("file_path")
    def validate_file_path(self, key: str, path: str) -> str:
        """
        Validate file path.

        Args:
            key: Field name ('file_path')
            path: File path to validate

        Returns:
            Validated file path

        Raises:
            ValueError: If path is empty
        """
        if not path:
            raise ValueError("File path is required")
        return path

    @validates("estimated_difficulty")
    def validate_difficulty(self, key: str, difficulty: int) -> int:
        """
        Validate difficulty rating.

        Args:
            key: Field name ('estimated_difficulty')
            difficulty: Difficulty rating to validate

        Returns:
            Validated difficulty rating

        Raises:
            ValueError: If difficulty is not between 1 and 10
        """
        if difficulty is not None and (difficulty < 1 or difficulty > 10):
            raise ValueError("Difficulty rating must be between 1 and 10")
        return difficulty

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Pattern instance to a dictionary.

        Returns:
            Dictionary representation of the pattern
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
            except:
                result["tags"] = []

        # Add component count
        result["component_count"] = len(self.components) if self.components else 0

        return result

    def __repr__(self) -> str:
        """Return string representation of the Pattern."""
        return f"<Pattern(id={self.id}, name='{self.name}', project_type={self.project_type})>"


class ProjectTemplate(AbstractBase, ValidationMixin, TimestampMixin):
    """
    ProjectTemplate model for reusable project templates.

    This model defines templates that can be used to create new projects,
    with predefined components, materials, and settings.

    Attributes:
        name: Template name
        description: Template description
        project_type: Type of project
        skill_level: Required skill level
        estimated_duration: Estimated time to complete
        estimated_cost: Estimated cost
        version: Template version
        is_public: Whether template is public
        tags: Tags for categorization
        notes: Additional notes
    """

    __tablename__ = "project_templates"
    __validated_fields__: ClassVar[Set[str]] = {"name"}

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_type = Column(Enum(ProjectType))
    skill_level = Column(Enum(SkillLevel))

    # Estimates
    estimated_duration = Column(Integer)  # in hours
    estimated_cost = Column(Float)

    # Metadata
    version = Column(String(20))
    is_public = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True)
    notes = Column(Text)

    # Relationships
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)

    pattern = relationship(
        "Pattern", back_populates="project_templates", foreign_keys=[pattern_id]
    )

    projects = relationship("Project", back_populates="project_template")
    recurring_projects = relationship("RecurringProject", back_populates="template")
    components = relationship("ProjectTemplateComponent", back_populates="template")

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate template name.

        Args:
            key: Field name ('name')
            name: Template name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Template name must be at least 3 characters")
        return name.strip()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ProjectTemplate instance to a dictionary.

        Returns:
            Dictionary representation of the project template
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.project_type:
            result["project_type"] = self.project_type.name
        if self.skill_level:
            result["skill_level"] = self.skill_level.name

        # Handle JSON fields
        if isinstance(result.get("tags"), str):
            import json

            try:
                result["tags"] = json.loads(result["tags"])
            except:
                result["tags"] = []

        return result

    def __repr__(self) -> str:
        """Return string representation of the ProjectTemplate."""
        return f"<ProjectTemplate(id={self.id}, name='{self.name}', project_type={self.project_type})>"


class ProjectTemplateComponent(AbstractBase):
    """
    ProjectTemplateComponent model linking templates to components.

    This model defines the components that make up a project template,
    with quantities and implementation details.

    Attributes:
        template_id: ID of the associated template
        component_id: ID of the component
        quantity: Number of this component needed
    """

    __tablename__ = "project_template_components"

    # Relationships
    template_id = Column(Integer, ForeignKey("project_templates.id"), nullable=False)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=False)
    quantity = Column(Integer, default=1)

    # Relationships
    template = relationship("ProjectTemplate", back_populates="components")
    component = relationship("Component", backref="template_components")

    def __repr__(self) -> str:
        """Return string representation of the ProjectTemplateComponent."""
        return f"<ProjectTemplateComponent(template_id={self.template_id}, component_id={self.component_id}, quantity={self.quantity})>"
