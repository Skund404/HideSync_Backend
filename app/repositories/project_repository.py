# File: app/repositories/project_repository.py

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.project import Project, ProjectComponent
from app.db.models.enums import ProjectStatus, ProjectType
from app.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """
    Repository for Project entity operations.

    Handles data access for projects and project-related queries, providing methods
    for managing projects throughout their lifecycle from creation to completion.
    This repository is central to the leathercraft workflow management.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ProjectRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Project

    def get_projects_by_status(
        self, status: ProjectStatus, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects by their status.

        Args:
            status (ProjectStatus): The project status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_projects_by_customer(
        self, customer_id: Union[int, str], skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects for a specific customer.

        Args:
            customer_id (Union[int, str]): ID of the customer (can be int ID or string reference)
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects for the specified customer
        """
        # Handle both integer IDs and string references
        if isinstance(customer_id, int):
            query = self.session.query(self.model).filter(
                self.model.customer_id == customer_id
            )
        else:
            query = self.session.query(self.model).filter(
                self.model.customer == customer_id
            )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_projects_by_type(
        self, project_type: ProjectType, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects by their type.

        Args:
            project_type (ProjectType): The type of project to retrieve
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects of the specified type
        """
        query = self.session.query(self.model).filter(self.model.type == project_type)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_projects_in_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects with due dates within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects due within the date range
        """
        query = self.session.query(self.model).filter(
            and_(self.model.dueDate >= start_date, self.model.dueDate <= end_date)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_projects(self, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        Get projects that are past their due date but not completed.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of overdue projects
        """
        now = datetime.now()
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.dueDate < now,
                    self.model.status != ProjectStatus.COMPLETED,
                    self.model.status != ProjectStatus.CANCELLED,
                )
            )
            .order_by(self.model.dueDate)
        )  # Order by due date (oldest first)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_upcoming_projects(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects due within the specified number of days.

        Args:
            days (int): Number of days to look ahead
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of upcoming projects
        """
        now = datetime.now()
        future = now + timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.dueDate >= now,
                    self.model.dueDate <= future,
                    self.model.status != ProjectStatus.COMPLETED,
                    self.model.status != ProjectStatus.CANCELLED,
                )
            )
            .order_by(self.model.dueDate)
        )  # Order by due date

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_projects_by_progress_range(
        self, min_progress: float, max_progress: float, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects with progress percentage in the specified range.

        Args:
            min_progress (float): Minimum progress percentage (0-100)
            max_progress (float): Maximum progress percentage (0-100)
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects within the progress range
        """
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.progress >= min_progress,
                    self.model.progress <= max_progress,
                )
            )
            .order_by(self.model.progress)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_projects_by_template(
        self, template_id: int, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects created from a specific template.

        Args:
            template_id (int): ID of the template
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of projects created from the template
        """
        query = self.session.query(self.model).filter(
            self.model.template_id == template_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_project_status(
        self, project_id: int, status: ProjectStatus
    ) -> Optional[Project]:
        """
        Update a project's status.

        Args:
            project_id (int): ID of the project
            status (ProjectStatus): New status to set

        Returns:
            Optional[Project]: Updated project if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        project.status = status

        # If project is completed, set the completion date
        if status == ProjectStatus.COMPLETED and not project.completedDate:
            project.completedDate = datetime.now()
            project.progress = 100
            project.completionPercentage = 100

        self.session.commit()
        self.session.refresh(project)
        return self._decrypt_sensitive_fields(project)

    def update_project_progress(
        self, project_id: int, progress: float
    ) -> Optional[Project]:
        """
        Update a project's progress percentage.

        Args:
            project_id (int): ID of the project
            progress (float): New progress value (0-100)

        Returns:
            Optional[Project]: Updated project if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        # Ensure progress is between 0 and 100
        project.progress = min(max(progress, 0), 100)
        project.completionPercentage = int(project.progress)

        # If progress is 100%, update status to completed if not already
        if project.progress >= 100 and project.status != ProjectStatus.COMPLETED:
            project.status = ProjectStatus.COMPLETED
            project.completedDate = datetime.now()

        self.session.commit()
        self.session.refresh(project)
        return self._decrypt_sensitive_fields(project)

    def get_project_with_components(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a project with its components.

        Args:
            project_id (int): ID of the project

        Returns:
            Optional[Dict[str, Any]]: Dictionary with project and components if found, None otherwise
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        # Get project components
        components = (
            self.session.query(ProjectComponent)
            .filter(ProjectComponent.project_id == project_id)
            .all()
        )

        return {"project": project, "components": components}

    def assign_component_to_project(
        self, project_id: int, component_id: int, quantity: int = 1
    ) -> Optional[ProjectComponent]:
        """
        Assign a component to a project.

        Args:
            project_id (int): ID of the project
            component_id (int): ID of the component
            quantity (int): Quantity of the component to use

        Returns:
            Optional[ProjectComponent]: Created project-component relationship if successful, None otherwise
        """
        # Check if project exists
        project = self.get_by_id(project_id)
        if not project:
            return None

        # Check if component already assigned to project
        existing = (
            self.session.query(ProjectComponent)
            .filter(
                and_(
                    ProjectComponent.project_id == project_id,
                    ProjectComponent.component_id == component_id,
                )
            )
            .first()
        )

        if existing:
            # Update quantity if already exists
            existing.quantity = quantity
            self.session.commit()
            self.session.refresh(existing)
            return existing
        else:
            # Create new relationship
            component_link = ProjectComponent(
                project_id=project_id, component_id=component_id, quantity=quantity
            )
            self.session.add(component_link)
            self.session.commit()
            self.session.refresh(component_link)
            return component_link

    def remove_component_from_project(self, project_id: int, component_id: int) -> bool:
        """
        Remove a component from a project.

        Args:
            project_id (int): ID of the project
            component_id (int): ID of the component

        Returns:
            bool: True if component was removed, False otherwise
        """
        # Find the component link
        component_link = (
            self.session.query(ProjectComponent)
            .filter(
                and_(
                    ProjectComponent.project_id == project_id,
                    ProjectComponent.component_id == component_id,
                )
            )
            .first()
        )

        if not component_link:
            return False

        # Delete the link
        self.session.delete(component_link)
        self.session.commit()
        return True

    def update_component_quantity(
        self, project_id: int, component_id: int, quantity: int
    ) -> Optional[ProjectComponent]:
        """
        Update the quantity of a component in a project.

        Args:
            project_id (int): ID of the project
            component_id (int): ID of the component
            quantity (int): New quantity

        Returns:
            Optional[ProjectComponent]: Updated project-component relationship if found, None otherwise
        """
        # Find the component link
        component_link = (
            self.session.query(ProjectComponent)
            .filter(
                and_(
                    ProjectComponent.project_id == project_id,
                    ProjectComponent.component_id == component_id,
                )
            )
            .first()
        )

        if not component_link:
            return None

        # Update quantity
        component_link.quantity = quantity
        self.session.commit()
        self.session.refresh(component_link)
        return component_link

    def search_projects(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Search for projects by name, description, or customer.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Project]: List of matching projects
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.customer.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_project_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about projects.

        Returns:
            Dict[str, Any]: Dictionary with project statistics
        """
        # Total projects
        total_count = self.session.query(func.count(self.model.id)).scalar() or 0

        # Projects by status
        status_counts = (
            self.session.query(
                self.model.status, func.count(self.model.id).label("count")
            )
            .group_by(self.model.status)
            .all()
        )

        # Projects by type
        type_counts = (
            self.session.query(
                self.model.type, func.count(self.model.id).label("count")
            )
            .group_by(self.model.type)
            .all()
        )

        # Active projects
        active_projects = (
            self.session.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.status != ProjectStatus.COMPLETED,
                    self.model.status != ProjectStatus.CANCELLED,
                )
            )
            .scalar()
            or 0
        )

        # Overdue projects
        now = datetime.now()
        overdue_projects = (
            self.session.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.dueDate < now,
                    self.model.status != ProjectStatus.COMPLETED,
                    self.model.status != ProjectStatus.CANCELLED,
                )
            )
            .scalar()
            or 0
        )

        # Average completion time (days)
        avg_completion_time = (
            self.session.query(
                func.avg(
                    func.julianday(self.model.completedDate)
                    - func.julianday(self.model.startDate)
                )
            )
            .filter(
                and_(
                    self.model.completedDate.isnot(None),
                    self.model.startDate.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        return {
            "total_count": total_count,
            "active_projects": active_projects,
            "overdue_projects": overdue_projects,
            "average_completion_time_days": float(avg_completion_time),
            "by_status": [
                {
                    "status": status.value if hasattr(status, "value") else str(status),
                    "count": count,
                }
                for status, count in status_counts
            ],
            "by_type": [
                {
                    "type": type_.value if hasattr(type_, "value") else str(type_),
                    "count": count,
                }
                for type_, count in type_counts
            ],
        }
