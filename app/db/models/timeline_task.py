# File: app/db/models/timeline_task.py
"""
Timeline task model for the Leathercraft ERP system.

This module defines the TimelineTask model for tracking project timeline
tasks, dependencies, and progress. It helps with project scheduling and
progress tracking.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin


class TimelineTask(AbstractBase, ValidationMixin, TimestampMixin):
    """
    TimelineTask model for project timeline tasks.

    This model represents individual tasks within a project timeline,
    with dependencies, scheduling, and progress tracking.

    Attributes:
        project_id: ID of the associated project
        name: Task name/description
        start_date: Scheduled start date
        end_date: Scheduled end date
        progress: Task progress (0-100)
        status: Current task status
        dependencies: IDs of prerequisite tasks
        is_critical_path: Whether task is on critical path
    """

    __tablename__ = "timeline_tasks"
    __validated_fields__: ClassVar[Set[str]] = {
        "project_id",
        "name",
        "start_date",
        "end_date",
    }

    # Relationships
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # Task information
    name = Column(String(255), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    progress = Column(Integer, default=0)  # 0-100
    status = Column(String(50), default="PENDING")

    # Dependencies and scheduling
    dependencies = Column(JSON, nullable=True)  # List of task IDs
    is_critical_path = Column(Boolean, default=False)

    # Relationships
    project = relationship("Project", back_populates="timeline_tasks")

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate task name.

        Args:
            key: Field name ('name')
            name: Task name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Task name must be at least 2 characters")
        return name.strip()

    @validates("start_date", "end_date")
    def validate_dates(self, key: str, value: datetime) -> datetime:
        """
        Validate task dates.

        Args:
            key: Field name
            value: Date to validate

        Returns:
            Validated date

        Raises:
            ValueError: If end_date is earlier than start_date
        """
        if (
            key == "end_date"
            and hasattr(self, "start_date")
            and self.start_date
            and value < self.start_date
        ):
            raise ValueError("End date cannot be earlier than start date")
        return value

    @validates("progress")
    def validate_progress(self, key: str, progress: int) -> int:
        """
        Validate task progress.

        Args:
            key: Field name ('progress')
            progress: Progress to validate

        Returns:
            Validated progress

        Raises:
            ValueError: If progress is not between 0 and 100
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        # Update status based on progress
        if progress == 0:
            self.status = "PENDING"
        elif progress < 100:
            self.status = "IN_PROGRESS"
        else:
            self.status = "COMPLETED"

        return progress

    @hybrid_property
    def duration_days(self) -> int:
        """
        Calculate task duration in days.

        Returns:
            Duration in days
        """
        if not self.start_date or not self.end_date:
            return 0

        delta = self.end_date - self.start_date
        return max(1, delta.days)

    @hybrid_property
    def is_overdue(self) -> bool:
        """
        Check if task is overdue.

        Returns:
            True if task is overdue, False otherwise
        """
        if not self.end_date or self.progress == 100:
            return False

        return datetime.now() > self.end_date

    @hybrid_property
    def days_remaining(self) -> Optional[int]:
        """
        Calculate days remaining until end date.

        Returns:
            Days remaining, or None if no end date
        """
        if not self.end_date:
            return None

        delta = self.end_date - datetime.now()
        return max(0, delta.days)

    def update_progress(self, progress: int, update_project: bool = True) -> None:
        """
        Update task progress.

        Args:
            progress: New progress value
            update_project: Whether to update project progress

        Raises:
            ValueError: If progress is not between 0 and 100
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        self.progress = progress

        # Update status based on progress
        if progress == 0:
            self.status = "PENDING"
        elif progress < 100:
            self.status = "IN_PROGRESS"
        else:
            self.status = "COMPLETED"

        # Update project progress if requested
        if (
            update_project
            and self.project
            and hasattr(self.project, "calculate_progress")
        ):
            self.project.calculate_progress()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert TimelineTask instance to a dictionary.

        Returns:
            Dictionary representation of the timeline task
        """
        result = super().to_dict()

        # Handle JSON fields
        if isinstance(result.get("dependencies"), str):
            import json

            try:
                result["dependencies"] = json.loads(result["dependencies"])
            except:
                result["dependencies"] = []

        # Add calculated properties
        result["duration_days"] = self.duration_days
        result["is_overdue"] = self.is_overdue
        result["days_remaining"] = self.days_remaining

        return result

    def __repr__(self) -> str:
        """Return string representation of the TimelineTask."""
        return f"<TimelineTask(id={self.id}, project_id={self.project_id}, name='{self.name}', progress={self.progress})>"
