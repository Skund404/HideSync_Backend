# File: app/services/project_template_service.py
"""
Project Template Service for HideSync.

Manages the lifecycle and operations of project templates,
including creation, updating, and template-based project generation.
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.base_service import BaseService
from app.db.models.project import ProjectTemplate, ProjectTemplateComponent
from app.db.models.enums import ProjectType
from app.repositories.project_template_repository import ProjectTemplateRepository
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.core.events import DomainEvent
from app.core.validation import validate_input, validate_entity


# Domain Events for Project Templates
class ProjectTemplateCreated(DomainEvent):
    """Event emitted when a project template is created."""

    def __init__(
        self, template_id: int, project_type: str, created_by: Optional[int] = None
    ):
        """
        Initialize project template created event.

        Args:
            template_id: ID of the created template
            project_type: Type of projects the template is for
            created_by: Optional ID of the user who created the template
        """
        super().__init__()
        self.template_id = template_id
        self.project_type = project_type
        self.created_by = created_by


class ProjectTemplateUpdated(DomainEvent):
    """Event emitted when a project template is updated."""

    def __init__(
        self,
        template_id: int,
        changes: Dict[str, Any],
        updated_by: Optional[int] = None,
    ):
        """
        Initialize project template updated event.

        Args:
            template_id: ID of the updated template
            changes: Dictionary of changed fields
            updated_by: Optional ID of the user who updated the template
        """
        super().__init__()
        self.template_id = template_id
        self.changes = changes
        self.updated_by = updated_by


class ProjectTemplateDeleted(DomainEvent):
    """Event emitted when a project template is deleted."""

    def __init__(self, template_id: int, deleted_by: Optional[int] = None):
        """
        Initialize project template deleted event.

        Args:
            template_id: ID of the deleted template
            deleted_by: Optional ID of the user who deleted the template
        """
        super().__init__()
        self.template_id = template_id
        self.deleted_by = deleted_by


# Validation function
validate_project_template = validate_entity(ProjectTemplate)


class ProjectTemplateService(BaseService[ProjectTemplate]):
    """
    Service for managing project templates in the HideSync system.

    Provides functionality for:
    - Project template creation and management
    - Component tracking for templates
    - Template-based project generation
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        component_service=None,
    ):
        """
        Initialize ProjectTemplateService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            component_service: Optional component service for component operations
        """
        self.session = session
        self.repository = repository or ProjectTemplateRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.component_service = component_service

    @validate_input(validate_project_template)
    def create_project_template(
        self, data: Dict[str, Any], user_id: Optional[int] = None
    ) -> ProjectTemplate:
        """
        Create a new project template.

        Args:
            data: Project template data
            user_id: ID of the user creating the template

        Returns:
            Created project template entity

        Raises:
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Set default values if not provided
            if "is_public" not in data:
                data["is_public"] = False

            if "version" not in data:
                data["version"] = "1.0"

            # Separate components if provided
            components = data.pop("components", [])

            # Create template
            template = self.repository.create(data)

            # Add components if provided
            for component_data in components:
                component_data["template_id"] = template.id
                self.add_template_component(template.id, component_data)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    ProjectTemplateCreated(
                        template_id=template.id,
                        project_type=template.project_type,
                        created_by=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate("ProjectTemplates")

            return template

    def get_project_template(self, template_id: int) -> ProjectTemplate:
        """
        Retrieve a project template by its ID.

        Args:
            template_id: ID of the project template

        Returns:
            Project template entity with components

        Raises:
            EntityNotFoundException: If template not found
        """
        template = self.repository.get_by_id(template_id)
        if not template:
            raise EntityNotFoundException(
                entity_name="ProjectTemplate", entity_id=template_id
            )

        # Fetch components if needed
        template.components = self.repository.get_template_components(template_id)
        return template

    def list_project_templates(
        self, skip: int = 0, limit: int = 100, filters: Optional[Dict[str, Any]] = None
    ) -> List[ProjectTemplate]:
        """
        List project templates with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional dictionary of filter parameters

        Returns:
            List of project templates
        """
        filters = filters or {}
        return self.repository.list(skip=skip, limit=limit, **filters)

    def update_project_template(
        self, template_id: int, data: Dict[str, Any], user_id: Optional[int] = None
    ) -> ProjectTemplate:
        """
        Update a project template.

        Args:
            template_id: ID of the template to update
            data: Updated template data
            user_id: ID of the user updating the template

        Returns:
            Updated project template entity

        Raises:
            EntityNotFoundException: If template not found
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Get original template for change tracking
            original_template = self.repository.get_by_id(template_id)
            if not original_template:
                raise EntityNotFoundException(
                    entity_name="ProjectTemplate", entity_id=template_id
                )

            # Separate components if provided
            components = data.pop("components", None)

            # Update template
            updated_template = self.repository.update(template_id, data)

            # Update components if provided
            if components is not None:
                # Remove existing components
                self.repository.remove_all_template_components(template_id)

                # Add new components
                for component_data in components:
                    component_data["template_id"] = template_id
                    self.add_template_component(template_id, component_data)

            # Publish event if event bus exists
            if self.event_bus:
                # Calculate changes
                changes = {}
                for key, new_value in data.items():
                    old_value = getattr(original_template, key, None)
                    if old_value != new_value:
                        changes[key] = {"old": old_value, "new": new_value}

                self.event_bus.publish(
                    ProjectTemplateUpdated(
                        template_id=template_id, changes=changes, updated_by=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate("ProjectTemplates")
                self.cache_service.invalidate(f"ProjectTemplate:{template_id}")

            return updated_template

    def delete_project_template(
        self, template_id: int, user_id: Optional[int] = None
    ) -> bool:
        """
        Delete a project template.

        Args:
            template_id: ID of the template to delete
            user_id: ID of the user deleting the template

        Returns:
            True if template was deleted, False otherwise

        Raises:
            BusinessRuleException: If template cannot be deleted
        """
        with self.transaction():
            # Check if template exists
            template = self.repository.get_by_id(template_id)
            if not template:
                raise EntityNotFoundException(
                    entity_name="ProjectTemplate", entity_id=template_id
                )

            # Check if template is used in any projects
            usage_count = self.repository.get_template_usage_count(template_id)
            if usage_count > 0:
                raise BusinessRuleException(
                    f"Cannot delete template. It has been used in {usage_count} projects."
                )

            # Delete template
            result = self.repository.delete(template_id)

            # Publish event if event bus exists
            if result and self.event_bus:
                self.event_bus.publish(
                    ProjectTemplateDeleted(template_id=template_id, deleted_by=user_id)
                )

            # Invalidate cache if cache service exists
            if result and self.cache_service:
                self.cache_service.invalidate("ProjectTemplates")

            return result

    def add_template_component(
        self, template_id: int, component_data: Dict[str, Any]
    ) -> ProjectTemplateComponent:
        """
        Add a component to a project template.

        Args:
            template_id: ID of the project template
            component_data: Component data to add

        Returns:
            Created project template component

        Raises:
            EntityNotFoundException: If template not found
            ValidationException: If component data is invalid
        """
        with self.transaction():
            # Ensure template exists
            template = self.repository.get_by_id(template_id)
            if not template:
                raise EntityNotFoundException(
                    entity_name="ProjectTemplate", entity_id=template_id
                )

            # Validate component data
            component_data["template_id"] = template_id
            component = self.repository.add_template_component(component_data)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"ProjectTemplate:{template_id}")

            return component

    def generate_project_from_template(
        self,
        template_id: int,
        customizations: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a new project from a template.

        Args:
            template_id: ID of the template to use
            customizations: Optional customizations to apply
            user_id: ID of the user generating the project

        Returns:
            Generated project with its components

        Raises:
            EntityNotFoundException: If template not found
        """
        with self.transaction():
            # Get template with its components
            template = self.get_project_template(template_id)

            # Prepare project creation data
            project_data = {
                "name": template.name,
                "description": template.description,
                "type": template.project_type,
                "template_id": template_id,
                # Apply any custom overrides
                **{
                    k: v
                    for k, v in (customizations or {}).items()
                    if k not in ["components", "template_id"]
                },
            }

            # Get project service to create the project
            from app.services.project_service import ProjectService

            project_service = ProjectService(self.session)

            # Prepare components from template
            components = [
                {"component_id": comp.component_id, "quantity": comp.quantity}
                for comp in template.components
            ]

            # Create project with components
            return project_service.create_project_with_components(
                project_data, components, user_id
            )

    def _create_created_event(self, entity: ProjectTemplate) -> DomainEvent:
        """
        Create event for project template creation.

        Args:
            entity: Created project template entity

        Returns:
            ProjectTemplateCreated event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return ProjectTemplateCreated(
            template_id=entity.id, project_type=entity.project_type, created_by=user_id
        )

    def _create_updated_event(
        self, original: ProjectTemplate, updated: ProjectTemplate
    ) -> DomainEvent:
        """
        Create event for project template update.

        Args:
            original: Original project template entity
            updated: Updated project template entity

        Returns:
            ProjectTemplateUpdated event
        """
        changes = {}
        for key, new_value in updated.__dict__.items():
            if key.startswith("_"):
                continue
            old_value = getattr(original, key, None)
            if old_value != new_value:
                changes[key] = {"old": old_value, "new": new_value}

        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return ProjectTemplateUpdated(
            template_id=updated.id, changes=changes, updated_by=user_id
        )

    def _create_deleted_event(self, entity: ProjectTemplate) -> DomainEvent:
        """
        Create event for project template deletion.

        Args:
            entity: Deleted project template entity

        Returns:
            ProjectTemplateDeleted event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return ProjectTemplateDeleted(template_id=entity.id, deleted_by=user_id)
