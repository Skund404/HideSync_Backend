# File: app/repositories/project_template_repository.py
"""
Project Template Repository for HideSync.

Handles data access and persistence operations for project templates
and their associated components.
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.repositories.base_repository import BaseRepository
from app.db.models.project import ProjectTemplate, ProjectTemplateComponent
from app.core.exceptions import EntityNotFoundException


class ProjectTemplateRepository(BaseRepository[ProjectTemplate]):
    """
    Repository for ProjectTemplate entity operations.

    Manages data access for project templates, including
    creating, retrieving, updating, and deleting templates
    along with their associated components.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ProjectTemplateRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ProjectTemplate

    def get_by_id(self, template_id: int) -> Optional[ProjectTemplate]:
        """
        Retrieve a project template by its ID with its components.

        Args:
            template_id (int): ID of the project template

        Returns:
            Optional[ProjectTemplate]: Project template with components if found
        """
        return (
            self.session.query(self.model)
            .options(joinedload(self.model.components))
            .filter(self.model.id == template_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[ProjectTemplate]:
        """
        List project templates with optional filtering and pagination.

        Args:
            skip (int): Number of records to skip
            limit (int): Maximum number of records to return
            **filters: Additional filter parameters

        Returns:
            List[ProjectTemplate]: List of project templates
        """
        query = self.session.query(self.model)

        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if key == "name":
                        # Case-insensitive name search
                        query = query.filter(
                            func.lower(getattr(self.model, key)).like(
                                f"%{value.lower()}%"
                            )
                        )
                    else:
                        query = query.filter(getattr(self.model, key) == value)

        # Order by creation date, most recent first
        query = query.order_by(self.model.created_at.desc())

        return query.offset(skip).limit(limit).all()

    def count(self, **filters) -> int:
        """
        Count project templates based on filters.

        Args:
            **filters: Optional filter parameters

        Returns:
            int: Number of project templates matching the filters
        """
        query = self.session.query(self.model)

        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

        return query.count()

    def get_template_components(
        self, template_id: int
    ) -> List[ProjectTemplateComponent]:
        """
        Retrieve components for a specific project template.

        Args:
            template_id (int): ID of the project template

        Returns:
            List[ProjectTemplateComponent]: List of template components
        """
        return (
            self.session.query(ProjectTemplateComponent)
            .filter(ProjectTemplateComponent.template_id == template_id)
            .all()
        )

    def add_template_component(
        self, component_data: Dict[str, Any]
    ) -> ProjectTemplateComponent:
        """
        Add a component to a project template.

        Args:
            component_data (Dict[str, Any]): Component data to add

        Returns:
            ProjectTemplateComponent: Created template component
        """
        component = ProjectTemplateComponent(**component_data)
        self.session.add(component)
        self.session.commit()
        self.session.refresh(component)
        return component

    def remove_all_template_components(self, template_id: int) -> None:
        """
        Remove all components from a project template.

        Args:
            template_id (int): ID of the project template
        """
        self.session.query(ProjectTemplateComponent).filter(
            ProjectTemplateComponent.template_id == template_id
        ).delete()
        self.session.commit()

    def get_template_usage_count(self, template_id: int) -> int:
        """
        Get the number of projects created from a specific template.

        Args:
            template_id (int): ID of the project template

        Returns:
            int: Number of projects using this template
        """
        # Import Project here to avoid circular import
        from app.db.models.project import Project

        return (
            self.session.query(func.count(Project.id))
            .filter(Project.template_id == template_id)
            .scalar()
            or 0
        )

    def search_templates(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Search project templates by name, description, or tags.

        Args:
            query (str): Search term
            skip (int): Number of records to skip
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of matching project templates
        """
        search_query = self.session.query(self.model).filter(
            or_(
                func.lower(self.model.name).like(f"%{query.lower()}%"),
                func.lower(self.model.description).like(f"%{query.lower()}%"),
                # If tags are stored as a string or JSON array
                func.lower(self.model.tags.astext).like(f"%{query.lower()}%"),
            )
        )

        return search_query.offset(skip).limit(limit).all()
