# File: app/repositories/recurring_project_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.recurring_project import (
    RecurringProject,
    RecurrencePattern,
    GeneratedProject,
)
from app.repositories.base_repository import BaseRepository


class RecurringProjectRepository(BaseRepository[RecurringProject]):
    """
    Repository for RecurringProject entity operations.

    Handles data access for recurring projects, which are projects that
    are scheduled to run at regular intervals based on a pattern.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RecurringProjectRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = RecurringProject

    def get_active_recurring_projects(
        self, skip: int = 0, limit: int = 100
    ) -> List[RecurringProject]:
        """
        Get active recurring projects.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[RecurringProject]: List of active recurring projects
        """
        query = self.session.query(self.model).filter(self.model.isActive == True)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recurring_projects_by_template(
        self, template_id: str, skip: int = 0, limit: int = 100
    ) -> List[RecurringProject]:
        """
        Get recurring projects based on a specific template.

        Args:
            template_id (str): ID of the template
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[RecurringProject]: List of recurring projects using the template
        """
        query = self.session.query(self.model).filter(
            self.model.templateId == template_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recurring_projects_by_client(
        self, client_id: str, skip: int = 0, limit: int = 100
    ) -> List[RecurringProject]:
        """
        Get recurring projects for a specific client.

        Args:
            client_id (str): ID of the client
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[RecurringProject]: List of recurring projects for the client
        """
        query = self.session.query(self.model).filter(self.model.clientId == client_id)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recurring_projects_due_for_generation(self) -> List[RecurringProject]:
        """
        Get recurring projects that are due for project generation.

        Returns:
            List[RecurringProject]: List of recurring projects due for generation
        """
        now = datetime.now().isoformat()

        query = self.session.query(self.model).filter(
            and_(
                self.model.isActive == True,
                self.model.nextOccurrence <= now,
                self.model.autoGenerate == True,
            )
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_recurring_project_status(
        self, project_id: str, is_active: bool
    ) -> Optional[RecurringProject]:
        """
        Update a recurring project's active status.

        Args:
            project_id (str): ID of the recurring project
            is_active (bool): New active status

        Returns:
            Optional[RecurringProject]: Updated recurring project if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        project.isActive = is_active
        project.modifiedAt = datetime.now()

        self.session.commit()
        self.session.refresh(project)
        return self._decrypt_sensitive_fields(project)

    def update_next_occurrence(
        self, project_id: str, next_occurrence: str
    ) -> Optional[RecurringProject]:
        """
        Update a recurring project's next occurrence date.

        Args:
            project_id (str): ID of the recurring project
            next_occurrence (str): New next occurrence date

        Returns:
            Optional[RecurringProject]: Updated recurring project if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        project.nextOccurrence = next_occurrence
        project.modifiedAt = datetime.now()

        self.session.commit()
        self.session.refresh(project)
        return self._decrypt_sensitive_fields(project)

    def get_recurring_project_with_pattern(
        self, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a recurring project with its recurrence pattern.

        Args:
            project_id (str): ID of the recurring project

        Returns:
            Optional[Dict[str, Any]]: Dictionary with project and pattern if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        # Get the recurrence pattern
        pattern = (
            self.session.query(RecurrencePattern)
            .filter(
                RecurrencePattern.id == project.id
            )  # Assuming pattern ID matches project ID
            .first()
        )

        return {"project": self._decrypt_sensitive_fields(project), "pattern": pattern}


class RecurrencePatternRepository(BaseRepository[RecurrencePattern]):
    """
    Repository for RecurrencePattern entity operations.

    Manages patterns that define how recurring projects are scheduled,
    including frequency, intervals, and date calculations.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RecurrencePatternRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = RecurrencePattern

    def get_patterns_by_frequency(
        self, frequency: str, skip: int = 0, limit: int = 100
    ) -> List[RecurrencePattern]:
        """
        Get recurrence patterns by frequency.

        Args:
            frequency (str): The frequency to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[RecurrencePattern]: List of patterns with the specified frequency
        """
        query = self.session.query(self.model).filter(self.model.frequency == frequency)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_active_patterns(
        self, skip: int = 0, limit: int = 100
    ) -> List[RecurrencePattern]:
        """
        Get active recurrence patterns (with future end dates).

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[RecurrencePattern]: List of active patterns
        """
        now = datetime.now().isoformat()

        query = self.session.query(self.model).filter(self.model.endDate >= now)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def calculate_next_occurrence(
        self, pattern_id: str, from_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Calculate the next occurrence date based on a pattern.

        Args:
            pattern_id (str): ID of the recurrence pattern
            from_date (Optional[datetime], optional): Date to calculate from, defaults to now

        Returns:
            Optional[datetime]: The next occurrence date, None if pattern not found or no more occurrences
        """
        pattern = self.get_by_id(pattern_id)
        if not pattern:
            return None

        if not from_date:
            from_date = datetime.now()

        # Logic to calculate next occurrence based on frequency and other parameters
        if pattern.frequency == "daily":
            next_date = from_date + timedelta(days=pattern.interval)
        elif pattern.frequency == "weekly":
            # Find next matching day of week
            days_ahead = 0
            for day in pattern.daysOfWeek or []:
                days_to_day = (day - from_date.weekday()) % 7
                if days_to_day > 0 and (days_ahead == 0 or days_to_day < days_ahead):
                    days_ahead = days_to_day

            if days_ahead == 0:  # No day found in current week, move to next week
                days_ahead = 7 * pattern.interval

            next_date = from_date + timedelta(days=days_ahead)
        elif pattern.frequency == "monthly":
            # Move to next month
            next_month = from_date.month + pattern.interval
            next_year = from_date.year + (next_month - 1) // 12
            next_month = ((next_month - 1) % 12) + 1

            # Use day of month or calculate based on week of month
            if pattern.dayOfMonth:
                # Ensure day exists in the month
                try:
                    next_date = datetime(next_year, next_month, pattern.dayOfMonth)
                except ValueError:
                    # If day doesn't exist in month, use last day of month
                    if next_month == 12:
                        next_date = datetime(next_year + 1, 1, 1) - timedelta(days=1)
                    else:
                        next_date = datetime(next_year, next_month + 1, 1) - timedelta(
                            days=1
                        )
            elif pattern.weekOfMonth and pattern.daysOfWeek:
                # Calculate based on week of month (e.g., 3rd Tuesday)
                day_of_week = pattern.daysOfWeek[0] if pattern.daysOfWeek else 0

                # Start with the first day of the month
                first_day = datetime(next_year, next_month, 1)

                # Find the first occurrence of the day of week
                days_ahead = (day_of_week - first_day.weekday()) % 7
                first_occurrence = first_day + timedelta(days=days_ahead)

                # Add weeks based on week of month (0-indexed)
                next_date = first_occurrence + timedelta(
                    days=(pattern.weekOfMonth - 1) * 7
                )
            else:
                # Default to same day of month
                day = min(from_date.day, 28)  # Avoid month boundary issues
                next_date = datetime(next_year, next_month, day)
        elif pattern.frequency == "yearly":
            # Move to next year
            next_year = from_date.year + pattern.interval
            try:
                next_date = datetime(
                    next_year,
                    pattern.month or from_date.month,
                    pattern.dayOfMonth or from_date.day,
                )
            except ValueError:
                # Handle February 29 in non-leap years
                if pattern.month == 2 and pattern.dayOfMonth == 29:
                    next_date = datetime(next_year, 2, 28)
                else:
                    raise
        elif pattern.frequency == "custom" and pattern.customDates:
            # Find the next date in the custom dates list
            for custom_date in pattern.customDates:
                date_obj = datetime.fromisoformat(custom_date)
                if date_obj > from_date:
                    next_date = date_obj
                    break
            else:
                return None  # No future custom dates
        else:
            return None  # Unrecognized frequency

        # Check if we've reached the end date or max occurrences
        if pattern.endDate and next_date > datetime.fromisoformat(pattern.endDate):
            return None

        return next_date


class GeneratedProjectRepository(BaseRepository[GeneratedProject]):
    """
    Repository for GeneratedProject entity operations.

    Manages projects that have been generated from recurring project templates,
    tracking their status, scheduling, and relationship to parent projects.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the GeneratedProjectRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = GeneratedProject

    def get_generated_projects_by_recurring_project(
        self, recurring_project_id: str
    ) -> List[GeneratedProject]:
        """
        Get generated projects for a specific recurring project.

        Args:
            recurring_project_id (str): ID of the recurring project

        Returns:
            List[GeneratedProject]: List of generated projects for the recurring project
        """
        query = self.session.query(self.model).filter(
            self.model.recurringProjectId == recurring_project_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_generated_projects_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[GeneratedProject]:
        """
        Get generated projects by status.

        Args:
            status (str): The status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[GeneratedProject]: List of generated projects with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_upcoming_generated_projects(
        self, days: int = 30, skip: int = 0, limit: int = 100
    ) -> List[GeneratedProject]:
        """
        Get upcoming generated projects scheduled within the specified number of days.

        Args:
            days (int): Number of days to look ahead
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[GeneratedProject]: List of upcoming generated projects
        """
        now = datetime.now()
        future = now + timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.scheduledDate >= now.isoformat(),
                    self.model.scheduledDate <= future.isoformat(),
                )
            )
            .order_by(self.model.scheduledDate)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_generated_project_status(
        self, project_id: str, status: str
    ) -> Optional[GeneratedProject]:
        """
        Update a generated project's status.

        Args:
            project_id (str): ID of the generated project
            status (str): New status to set

        Returns:
            Optional[GeneratedProject]: Updated generated project if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        project.status = status

        self.session.commit()
        self.session.refresh(project)
        return self._decrypt_sensitive_fields(project)
