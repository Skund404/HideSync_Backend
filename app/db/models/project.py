# File: app/db/models/project.py
"""
Project model for the Leathercraft ERP system.

This module defines the Project model, which represents custom leatherworking
projects and production items. Projects track the full workflow from concept
to completion, including materials, timelines, and customer requirements.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum,
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ProjectStatus, ProjectType


class Project(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Project model representing leatherworking projects.

    This model tracks all aspects of a leatherworking project, including
    customer information, timeline, materials, components, and workflow status.

    Attributes:
        name: Project name/description
        description: Detailed project description
        type: Type of leatherwork project
        status: Current workflow status
        start_date: Scheduled start date
        due_date: Deadline for completion
        completed_date: Actual completion date
        progress: Numeric progress indicator (0-100)
        completion_percentage: Calculated completion percentage
        sales_id: Associated sale record ID
        template_id: Project template ID (if created from template)
        customer: Customer name (denormalized for convenience)
        notes: Additional project notes
    """

    __tablename__ = "projects"
    __validated_fields__: ClassVar[Set[str]] = {"name", "due_date"}

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(Enum(ProjectType))
    status = Column(Enum(ProjectStatus), default=ProjectStatus.CONCEPT)

    # Timeline
    start_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    progress = Column(Float, default=0)  # 0-100 progress indicator

    # Relationships
    sales_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("project_templates.id"), nullable=True)

    # Additional information
    customer = Column(String(255), nullable=True)
    notes = Column(Text)

    # Relationships
    sale = relationship("Sale", back_populates="projects")
    project_template = relationship("ProjectTemplate", back_populates="projects")
    components = relationship(
        "ProjectComponent", back_populates="project", cascade="all, delete-orphan"
    )
    picking_lists = relationship("PickingList", back_populates="project")
    timeline_tasks = relationship(
        "TimelineTask", back_populates="project", cascade="all, delete-orphan"
    )
    tool_checkouts = relationship("ToolCheckout", back_populates="project")

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate project name.

        Args:
            key: Field name ('name')
            name: Project name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Project name must be at least 3 characters")
        return name.strip()

    @validates("due_date")
    def validate_due_date(
        self, key: str, due_date: Optional[datetime]
    ) -> Optional[datetime]:
        """
        Validate project due date.

        Args:
            key: Field name ('due_date')
            due_date: Due date to validate

        Returns:
            Validated due date

        Raises:
            ValueError: If due date is in the past
        """
        if due_date and due_date.date() < date.today():
            raise ValueError("Due date cannot be in the past")
        return due_date

    @validates("progress")
    def validate_progress(self, key: str, progress: float) -> float:
        """
        Validate progress value and update status when appropriate.

        Args:
            key: Field name ('progress')
            progress: Progress value (0-100)

        Returns:
            Validated progress value

        Raises:
            ValueError: If progress is not between 0 and 100
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        # Update status based on progress
        if progress == 100 and self.status != ProjectStatus.COMPLETED:
            self.status = ProjectStatus.COMPLETED
            self.completed_date = datetime.now()

        return progress

    @hybrid_property
    def is_overdue(self) -> bool:
        """
        Check if the project is overdue.

        Returns:
            True if the project is overdue, False otherwise
        """
        if not self.due_date:
            return False

        if self.status == ProjectStatus.COMPLETED and self.completed_date:
            return self.completed_date > self.due_date

        return datetime.now() > self.due_date and self.status != ProjectStatus.COMPLETED

    @hybrid_property
    def days_to_deadline(self) -> Optional[int]:
        """
        Calculate days remaining until the deadline.

        Returns:
            Number of days until deadline, or None if no deadline
        """
        if not self.due_date:
            return None

        delta = self.due_date.date() - date.today()
        return delta.days

    def calculate_progress(self) -> float:
        """
        Calculate progress based on completed tasks.

        Returns:
            Calculated progress percentage (0-100)
        """
        if not self.timeline_tasks:
            return self.progress

        total_tasks = len(self.timeline_tasks)
        if total_tasks == 0:
            return 0

        completed_tasks = sum(1 for task in self.timeline_tasks if task.progress == 100)

        progress_sum = sum(task.progress for task in self.timeline_tasks)
        calculated_progress = progress_sum / total_tasks

        # Update the stored progress
        self.progress = calculated_progress
        return calculated_progress

    def update_status(
        self, new_status: ProjectStatus, user: str, notes: Optional[str] = None
    ) -> None:
        """
        Update project status with audit trail.

        Args:
            new_status: New project status
            user: User making the change
            notes: Optional notes about the status change
        """
        old_status = self.status
        self.status = new_status

        # Record the change in history
        if hasattr(self, "record_change"):
            self.record_change(
                user,
                {
                    "field": "status",
                    "old_value": old_status.name if old_status else None,
                    "new_value": new_status.name,
                    "notes": notes,
                },
            )

        # Update dates based on status
        if new_status == ProjectStatus.IN_PROGRESS and not self.start_date:
            self.start_date = datetime.now()
        elif new_status == ProjectStatus.COMPLETED and not self.completed_date:
            self.completed_date = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Project instance to a dictionary.

        Returns:
            Dictionary representation of the project
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.type:
            result["type"] = self.type.name
        if self.status:
            result["status"] = self.status.name

        # Add calculated properties
        result["is_overdue"] = self.is_overdue
        result["days_to_deadline"] = self.days_to_deadline

        return result

    def __repr__(self) -> str:
        """Return string representation of the Project."""
        return f"<Project(id={self.id}, name='{self.name}', status={self.status}, progress={self.progress})>"


class ProjectComponent(AbstractBase, ValidationMixin):
    """
    ProjectComponent model representing components used in a project.

    This model tracks the components (parts) used in a project, including
    quantities and specific implementation details.

    Attributes:
        project_id: ID of the associated project
        component_id: ID of the component definition
        quantity: Number of this component needed
    """

    __tablename__ = "project_components"

    # Relationships
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=False)
    quantity = Column(Integer, default=1)

    # Relationships
    project = relationship("Project", back_populates="components")
    component = relationship("Component", back_populates="project_components")

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: int) -> int:
        """
        Validate component quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is less than 1
        """
        if quantity < 1:
            raise ValueError("Component quantity must be at least 1")
        return quantity

    def __repr__(self) -> str:
        """Return string representation of the ProjectComponent."""
        return f"<ProjectComponent(project_id={self.project_id}, component_id={self.component_id}, quantity={self.quantity})>"
