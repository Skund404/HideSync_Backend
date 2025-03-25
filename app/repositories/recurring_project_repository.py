# app/repositories/recurring_project_repository.py
"""
Repository implementations for recurring projects, recurrence patterns, and generated projects.

This module provides data access via the repository pattern for the
recurring project domain models.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.repositories.base_repository import BaseRepository
from app.db.models.recurring_project import (
    RecurringProject,
    RecurrencePattern,
    GeneratedProject,
)


class RecurringProjectRepository(BaseRepository[RecurringProject]):
    """Repository for recurring project entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RecurringProjectRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = RecurringProject

    def list(
        self, skip: int = 0, limit: int = 100, **filters
    ) -> List[RecurringProject]:
        """
        List recurring projects with filters.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria

        Returns:
            List of matching recurring projects
        """
        query = self.session.query(self.model)

        # Apply standard filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Handle range filters
        if "next_occurrence_gte" in filters:
            query = query.filter(
                self.model.next_occurrence >= filters["next_occurrence_gte"]
            )

        if "next_occurrence_lte" in filters:
            query = query.filter(
                self.model.next_occurrence <= filters["next_occurrence_lte"]
            )

        if "created_at_gte" in filters:
            query = query.filter(self.model.created_at >= filters["created_at_gte"])

        if "created_at_lte" in filters:
            query = query.filter(self.model.created_at <= filters["created_at_lte"])

        # Apply pagination
        query = query.order_by(self.model.created_at.desc())
        query = query.offset(skip).limit(limit)

        return query.all()

    def find_by_template(self, template_id: str) -> List[RecurringProject]:
        """
        Find recurring projects by template ID.

        Args:
            template_id: ID of the template to find projects for

        Returns:
            List of recurring projects using the template
        """
        return (
            self.session.query(self.model)
            .filter(self.model.template_id == template_id)
            .all()
        )


class RecurrencePatternRepository(BaseRepository[RecurrencePattern]):
    """Repository for recurrence pattern entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RecurrencePatternRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = RecurrencePattern


class GeneratedProjectRepository(BaseRepository[GeneratedProject]):
    """Repository for generated project entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the GeneratedProjectRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = GeneratedProject

    def find_by_date(
        self, recurring_project_id: str, scheduled_date: date
    ) -> Optional[GeneratedProject]:
        """
        Find a generated project by recurring project ID and scheduled date.

        Args:
            recurring_project_id: ID of the recurring project
            scheduled_date: Scheduled date to check

        Returns:
            Generated project if found, None otherwise
        """
        return (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.recurring_project_id == recurring_project_id,
                    self.model.scheduled_date == scheduled_date,
                )
            )
            .first()
        )

    def find_by_project(self, project_id: str) -> Optional[GeneratedProject]:
        """
        Find a generated project by the ID of its generated project.

        Args:
            project_id: ID of the generated project

        Returns:
            Generated project record if found, None otherwise
        """
        return (
            self.session.query(self.model)
            .filter(self.model.project_id == project_id)
            .first()
        )
