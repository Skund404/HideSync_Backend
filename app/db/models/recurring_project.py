# File: app/db/models/recurring_project.py
"""
Recurring project models for the Leathercraft ERP system.

This module defines the RecurringProject, RecurrencePattern, and
GeneratedProject models for automating recurring project creation
based on schedules and templates.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime, timedelta, date

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ProjectType, SkillLevel


class RecurrencePattern(AbstractBase, ValidationMixin):
    """
    RecurrencePattern model for defining recurring schedules.

    This model defines patterns for recurring events, such as daily,
    weekly, monthly, etc., with various configuration options.

    Attributes:
        name: Pattern name/description
        frequency: Recurrence frequency
        interval: Interval between occurrences
        start_date: Pattern start date
        end_date: Pattern end date
        end_after_occurrences: Number of occurrences before ending
        days_of_week: Days of week for weekly patterns
        day_of_month: Day of month for monthly patterns
        week_of_month: Week of month for monthly patterns
        month: Month for yearly patterns
        custom_dates: List of custom dates
        skip_weekends: Whether to skip weekends
        skip_holidays: Whether to skip holidays
    """

    __tablename__ = "recurrence_patterns"
    __validated_fields__: ClassVar[Set[str]] = {"name", "frequency"}

    # Basic information
    name = Column(String(100), nullable=False)
    frequency = Column(
        String(50), nullable=False
    )  # daily, weekly, monthly, quarterly, yearly, custom

    # Interval settings
    interval = Column(Integer, default=1)  # e.g., every 2 weeks
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    end_after_occurrences = Column(Integer, nullable=True)

    # Specific frequency settings
    days_of_week = Column(JSON, nullable=True)  # [0, 1, 2] - Monday, Tuesday, Wednesday
    day_of_month = Column(Integer, nullable=True)
    week_of_month = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    custom_dates = Column(JSON, nullable=True)  # ["2023-01-01", "2023-02-15"]

    # Skip options
    skip_weekends = Column(Boolean, default=False)
    skip_holidays = Column(Boolean, default=False)

    # Relationships
    recurring_projects = relationship(
        "RecurringProject", back_populates="recurrence_pattern"
    )

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
        if not name or len(name.strip()) < 2:
            raise ValueError("Pattern name must be at least 2 characters")
        return name.strip()

    @validates("frequency")
    def validate_frequency(self, key: str, frequency: str) -> str:
        """
        Validate frequency value.

        Args:
            key: Field name ('frequency')
            frequency: Frequency to validate

        Returns:
            Validated frequency

        Raises:
            ValueError: If frequency is not valid
        """
        valid_frequencies = [
            "daily",
            "weekly",
            "monthly",
            "quarterly",
            "yearly",
            "custom",
        ]
        if frequency not in valid_frequencies:
            raise ValueError(
                f"Frequency must be one of: {', '.join(valid_frequencies)}"
            )
        return frequency

    @validates("interval")
    def validate_interval(self, key: str, interval: int) -> int:
        """
        Validate interval value.

        Args:
            key: Field name ('interval')
            interval: Interval to validate

        Returns:
            Validated interval

        Raises:
            ValueError: If interval is less than 1
        """
        if interval < 1:
            raise ValueError("Interval must be at least 1")
        return interval

    def get_next_occurrence(
        self, after_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Calculate next occurrence based on pattern.

        Args:
            after_date: Date to start from (defaults to today)

        Returns:
            Next occurrence date, or None if pattern is complete
        """
        if after_date is None:
            after_date = datetime.now()

        # Check if pattern has ended
        if self.end_date and after_date > self.end_date:
            return None

        # Use custom dates if frequency is custom
        if self.frequency == "custom" and self.custom_dates:
            try:
                custom_dates = self.custom_dates
                if isinstance(custom_dates, str):
                    import json

                    custom_dates = json.loads(custom_dates)

                future_dates = [
                    datetime.fromisoformat(d)
                    for d in custom_dates
                    if datetime.fromisoformat(d) > after_date
                ]
                future_dates.sort()

                if future_dates:
                    return future_dates[0]
                return None
            except (ValueError, TypeError, json.JSONDecodeError):
                return None

        # Calculate next occurrence based on frequency
        next_date = None

        if self.frequency == "daily":
            next_date = after_date + timedelta(days=self.interval)

        elif self.frequency == "weekly":
            # Find next matching day of week
            days_to_check = self.days_of_week or [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
            ]  # Default to all days

            if isinstance(days_to_check, str):
                import json

                try:
                    days_to_check = json.loads(days_to_check)
                except json.JSONDecodeError:
                    days_to_check = [0, 1, 2, 3, 4, 5, 6]

            # Convert to int list if needed
            days_to_check = [int(d) for d in days_to_check if str(d).isdigit()]

            # Start from tomorrow
            check_date = after_date + timedelta(days=1)

            # Check up to 7*interval days to find the next match
            for _ in range(7 * self.interval):
                if check_date.weekday() in days_to_check:
                    next_date = check_date
                    break
                check_date += timedelta(days=1)

        elif self.frequency == "monthly":
            # Start with same day next month
            current_day = after_date.day
            target_day = self.day_of_month or current_day

            # Get first day of next month
            if after_date.month == 12:
                next_month = 1
                next_year = after_date.year + 1
            else:
                next_month = after_date.month + 1
                next_year = after_date.year

            # Create next month date with correct day
            import calendar

            _, last_day = calendar.monthrange(next_year, next_month)
            actual_day = min(target_day, last_day)

            next_date = datetime(
                next_year,
                next_month,
                actual_day,
                after_date.hour,
                after_date.minute,
                after_date.second,
            )

        elif self.frequency == "quarterly":
            # Add 3 months
            month = after_date.month
            year = after_date.year

            # Calculate next quarter
            month += 3 * self.interval
            while month > 12:
                month -= 12
                year += 1

            # Create date for first day of quarter
            import calendar

            _, last_day = calendar.monthrange(year, month)
            day = min(after_date.day, last_day)

            next_date = datetime(
                year, month, day, after_date.hour, after_date.minute, after_date.second
            )

        elif self.frequency == "yearly":
            # Add years
            next_date = datetime(
                after_date.year + self.interval,
                self.month or after_date.month,
                after_date.day,
                after_date.hour,
                after_date.minute,
                after_date.second,
            )

        # Handle weekend and holiday skipping
        if next_date:
            # Skip weekends if needed
            if self.skip_weekends and next_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                if next_date.weekday() == 5:  # Saturday
                    next_date += timedelta(days=2)  # Skip to Monday
                else:  # Sunday
                    next_date += timedelta(days=1)  # Skip to Monday

            # Skip holidays (implementation depends on holiday calendar)
            if self.skip_holidays:
                # Placeholder for holiday skipping
                pass

        return next_date

    def get_occurrences(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[datetime]:
        """
        Get list of occurrences within a range.

        Args:
            start: Start date (defaults to pattern start_date)
            end: End date (defaults to pattern end_date or none)
            limit: Maximum number of occurrences to return

        Returns:
            List of occurrence dates
        """
        occurrences = []

        if start is None:
            start = self.start_date

        current = start

        # Generate occurrences until we hit the limit, end date, or no more occurrences
        while len(occurrences) < limit:
            next_occurrence = self.get_next_occurrence(current)

            if not next_occurrence:
                break

            if end and next_occurrence > end:
                break

            occurrences.append(next_occurrence)
            current = next_occurrence

        return occurrences

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert RecurrencePattern instance to a dictionary.

        Returns:
            Dictionary representation of the recurrence pattern
        """
        result = super().to_dict()

        # Handle JSON fields
        for field in ["days_of_week", "custom_dates"]:
            if isinstance(result.get(field), str):
                import json

                try:
                    result[field] = json.loads(result[field])
                except:
                    result[field] = []

        # Add next few occurrences
        result["next_occurrences"] = [
            d.isoformat() for d in self.get_occurrences(limit=5)
        ]

        return result

    def __repr__(self) -> str:
        """Return string representation of the RecurrencePattern."""
        return f"<RecurrencePattern(id={self.id}, name='{self.name}', frequency='{self.frequency}')>"


class RecurringProject(AbstractBase, ValidationMixin, TimestampMixin):
    """
    RecurringProject model for automated project creation.

    This model defines projects that should be automatically created
    on a recurring schedule, based on a template and recurrence pattern.

    Attributes:
        template_id: ID of the project template
        name: Project name/description
        description: Detailed project description
        project_type: Type of project
        skill_level: Required skill level
        duration: Estimated duration
        is_active: Whether this recurring project is active
        next_occurrence: Next scheduled occurrence
        last_occurrence: Last occurrence
        total_occurrences: Total occurrences so far
        auto_generate: Whether to automatically generate projects
        advance_notice_days: Days of advance notice
        project_suffix: Suffix for generated project names
        client_id: Associated client/customer ID
        created_by: Creator of the recurring project
    """

    __tablename__ = "recurring_projects"
    __validated_fields__: ClassVar[Set[str]] = {
        "name",
        "template_id",
        "recurrence_pattern_id",
    }

    # Template information
    template_id = Column(Integer, ForeignKey("project_templates.id"), nullable=False)

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_type = Column(Enum(ProjectType))
    skill_level = Column(Enum(SkillLevel))
    duration = Column(Integer)  # in hours

    # Status and scheduling
    is_active = Column(Boolean, default=True)
    next_occurrence = Column(String(50))  # ISO date string
    last_occurrence = Column(String(50))  # ISO date string
    total_occurrences = Column(Integer, default=0)

    # Generation settings
    auto_generate = Column(Boolean, default=True)
    advance_notice_days = Column(Integer, default=7)
    project_suffix = Column(String(100))

    # Assignment
    client_id = Column(String(36))
    created_by = Column(String(100))

    # Relationships
    recurrence_pattern_id = Column(
        Integer, ForeignKey("recurrence_patterns.id"), nullable=False
    )
    recurrence_pattern = relationship(
        "RecurrencePattern", back_populates="recurring_projects"
    )
    template = relationship("ProjectTemplate", back_populates="recurring_projects")
    generated_projects = relationship(
        "GeneratedProject",
        back_populates="recurring_project",
        cascade="all, delete-orphan",
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate recurring project name.

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

    def update_next_occurrence(self) -> Optional[datetime]:
        """
        Update next occurrence based on recurrence pattern.

        Returns:
            Next occurrence date, or None if no more occurrences
        """
        if not self.recurrence_pattern:
            return None

        # Use last occurrence as reference, or now if none
        reference_date = None
        if self.last_occurrence:
            try:
                reference_date = datetime.fromisoformat(self.last_occurrence)
            except (ValueError, TypeError):
                reference_date = datetime.now()
        else:
            reference_date = datetime.now()

        # Get next occurrence from pattern
        next_date = self.recurrence_pattern.get_next_occurrence(reference_date)

        # Update next_occurrence field
        if next_date:
            self.next_occurrence = next_date.isoformat()
        else:
            self.next_occurrence = None

        return next_date

    def generate_project(
        self, scheduled_date: datetime, creator: str
    ) -> "GeneratedProject":
        """
        Generate a project for a specific date.

        Args:
            scheduled_date: Date for the project
            creator: Person generating the project

        Returns:
            GeneratedProject record

        Raises:
            ValueError: If project cannot be generated
        """
        from app.db.models.project import Project

        # Check if project already exists for this date
        for generated in self.generated_projects:
            if (
                generated.scheduled_date == scheduled_date.isoformat()
                and generated.status != "failed"
                and generated.status != "skipped"
            ):
                raise ValueError(f"Project already generated for {scheduled_date}")

        # Create a new project
        suffix = self.project_suffix or scheduled_date.strftime("%Y-%m-%d")
        project_name = f"{self.name} - {suffix}"

        project = Project(
            name=project_name,
            description=self.description,
            type=self.project_type,
            status="PLANNED",
            start_date=scheduled_date,
            due_date=scheduled_date
            + timedelta(hours=self.duration if self.duration else 8),
            template_id=self.template_id,
            customer=self.client_id,
        )

        # Record generated project
        occurrence_num = self.total_occurrences + 1
        self.total_occurrences = occurrence_num
        self.last_occurrence = scheduled_date.isoformat()

        generated_project = GeneratedProject(
            project_id=project.id,
            recurring_project_id=self.id,
            occurrence_number=occurrence_num,
            scheduled_date=scheduled_date.isoformat(),
            actual_generation_date=datetime.now().isoformat(),
            status="generated",
            notes=f"Generated by {creator}",
        )

        # Update next occurrence
        self.update_next_occurrence()

        return generated_project

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert RecurringProject instance to a dictionary.

        Returns:
            Dictionary representation of the recurring project
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.project_type:
            result["project_type"] = self.project_type.name
        if self.skill_level:
            result["skill_level"] = self.skill_level.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the RecurringProject."""
        return f"<RecurringProject(id={self.id}, name='{self.name}', active={self.is_active})>"


class GeneratedProject(AbstractBase, ValidationMixin, TimestampMixin):
    """
    GeneratedProject model for tracking generated recurring projects.

    This model tracks projects that have been automatically generated
    from recurring project definitions, including their status and dates.

    Attributes:
        project_id: ID of the generated project
        recurring_project_id: ID of the recurring project definition
        occurrence_number: Occurrence sequence number
        scheduled_date: Scheduled generation date
        actual_generation_date: Actual generation date
        status: Generation status
        notes: Additional notes
    """

    __tablename__ = "generated_projects"
    __validated_fields__: ClassVar[Set[str]] = {
        "recurring_project_id",
        "scheduled_date",
    }

    # Relationships
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    recurring_project_id = Column(
        Integer, ForeignKey("recurring_projects.id"), nullable=False
    )

    # Generation information
    occurrence_number = Column(Integer, nullable=False)
    scheduled_date = Column(String(50), nullable=False)  # ISO date string
    actual_generation_date = Column(String(50))  # ISO date string
    status = Column(
        String(20), default="scheduled"
    )  # scheduled, generated, skipped, failed
    notes = Column(Text)

    # Relationships
    project = relationship("Project", back_populates="generated_from")
    recurring_project = relationship(
        "RecurringProject", back_populates="generated_projects"
    )

    def mark_skipped(self, reason: str) -> None:
        """
        Mark project generation as skipped.

        Args:
            reason: Reason for skipping
        """
        self.status = "skipped"
        self.actual_generation_date = datetime.now().isoformat()

        if self.notes:
            self.notes += f"\nSkipped: {reason}"
        else:
            self.notes = f"Skipped: {reason}"

    def mark_failed(self, error: str) -> None:
        """
        Mark project generation as failed.

        Args:
            error: Error message
        """
        self.status = "failed"
        self.actual_generation_date = datetime.now().isoformat()

        if self.notes:
            self.notes += f"\nFailed: {error}"
        else:
            self.notes = f"Failed: {error}"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert GeneratedProject instance to a dictionary.

        Returns:
            Dictionary representation of the generated project
        """
        result = super().to_dict()

        # Add project name if available
        if hasattr(self, "project") and self.project:
            result["project_name"] = self.project.name

        # Add recurring project name if available
        if hasattr(self, "recurring_project") and self.recurring_project:
            result["recurring_project_name"] = self.recurring_project.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the GeneratedProject."""
        return f"<GeneratedProject(id={self.id}, recurring_project_id={self.recurring_project_id}, status='{self.status}')>"
