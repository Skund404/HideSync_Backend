# File: app/services/project_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta

from app.services.base_service import BaseService
from app.db.models.project import Project, ProjectComponent
from app.db.models.enums import ProjectStatus, ProjectType
from app.repositories.project_repository import ProjectRepository
from app.repositories.timeline_task_repository import TimelineTaskRepository
from app.core.exceptions import (
    ProjectNotFoundException,
    ValidationException,
    InvalidProjectStatusTransitionException,
    EntityNotFoundException,
    MaterialNotFoundException,
)
from app.core.events import DomainEvent
from app.core.validation import validate_input, validate_entity


# Domain events
class ProjectCreated(DomainEvent):
    """Event emitted when a project is created."""

    def __init__(
        self,
        project_id: int,
        project_type: str,
        customer_id: Optional[int],
        user_id: Optional[int] = None,
    ):
        """
        Initialize project created event.

        Args:
            project_id: ID of the created project
            project_type: Type of the created project
            customer_id: Optional ID of the associated customer
            user_id: Optional ID of the user who created the project
        """
        super().__init__()
        self.project_id = project_id
        self.project_type = project_type
        self.customer_id = customer_id
        self.user_id = user_id


class ProjectStatusChanged(DomainEvent):
    """Event emitted when a project's status changes."""

    def __init__(
        self,
        project_id: int,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize project status changed event.

        Args:
            project_id: ID of the project
            previous_status: Previous status
            new_status: New status
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.project_id = project_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


class ProjectComponentAdded(DomainEvent):
    """Event emitted when a component is added to a project."""

    def __init__(
        self,
        project_id: int,
        component_id: int,
        quantity: int,
        user_id: Optional[int] = None,
    ):
        """
        Initialize project component added event.

        Args:
            project_id: ID of the project
            component_id: ID of the added component
            quantity: Quantity of the component
            user_id: Optional ID of the user who added the component
        """
        super().__init__()
        self.project_id = project_id
        self.component_id = component_id
        self.quantity = quantity
        self.user_id = user_id


class ProjectUpdated(DomainEvent):
    """Event emitted when a project is updated."""

    def __init__(
        self, project_id: int, changes: Dict[str, Any], user_id: Optional[int] = None
    ):
        """
        Initialize project updated event.

        Args:
            project_id: ID of the updated project
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the project
        """
        super().__init__()
        self.project_id = project_id
        self.changes = changes
        self.user_id = user_id


class ProjectDeleted(DomainEvent):
    """Event emitted when a project is deleted."""

    def __init__(self, project_id: int, user_id: Optional[int] = None):
        """
        Initialize project deleted event.

        Args:
            project_id: ID of the deleted project
            user_id: Optional ID of the user who deleted the project
        """
        super().__init__()
        self.project_id = project_id
        self.user_id = user_id


class TimelineTaskCreated(DomainEvent):
    """Event emitted when a timeline task is created."""

    def __init__(
        self,
        task_id: str,
        project_id: int,
        task_name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize timeline task created event.

        Args:
            task_id: ID of the created task
            project_id: ID of the associated project
            task_name: Name of the task
            user_id: Optional ID of the user who created the task
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.task_name = task_name
        self.user_id = user_id


class TimelineTaskUpdated(DomainEvent):
    """Event emitted when a timeline task is updated."""

    def __init__(
        self,
        task_id: str,
        project_id: int,
        changes: Dict[str, Any],
        user_id: Optional[int] = None,
    ):
        """
        Initialize timeline task updated event.

        Args:
            task_id: ID of the updated task
            project_id: ID of the associated project
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the task
        """
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id
        self.changes = changes
        self.user_id = user_id


# Validation functions
validate_project = validate_entity(Project)
validate_project_component = validate_entity(ProjectComponent)

# Valid status transitions (from status -> list of possible next statuses)
VALID_STATUS_TRANSITIONS = {
    ProjectStatus.CONCEPT.value: [
        ProjectStatus.PLANNING.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.PLANNING.value: [
        ProjectStatus.DESIGN_PHASE.value,
        ProjectStatus.MATERIAL_SELECTION.value,
        ProjectStatus.PRODUCTION_QUEUE.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.DESIGN_PHASE.value: [
        ProjectStatus.PLANNING.value,
        ProjectStatus.CLIENT_APPROVAL.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.CLIENT_APPROVAL.value: [
        ProjectStatus.DESIGN_PHASE.value,
        ProjectStatus.MATERIAL_SELECTION.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.MATERIAL_SELECTION.value: [
        ProjectStatus.MATERIAL_PURCHASED.value,
        ProjectStatus.WAITING_FOR_MATERIALS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.MATERIAL_PURCHASED.value: [
        ProjectStatus.PRODUCTION_QUEUE.value,
        ProjectStatus.WAITING_FOR_MATERIALS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.WAITING_FOR_MATERIALS.value: [
        ProjectStatus.PRODUCTION_QUEUE.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.PRODUCTION_QUEUE.value: [
        ProjectStatus.CUTTING.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.CUTTING.value: [
        ProjectStatus.ASSEMBLY.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.ASSEMBLY.value: [
        ProjectStatus.STITCHING.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.STITCHING.value: [
        ProjectStatus.EDGE_FINISHING.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.EDGE_FINISHING.value: [
        ProjectStatus.HARDWARE_INSTALLATION.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.HARDWARE_INSTALLATION.value: [
        ProjectStatus.QUALITY_CHECK.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.IN_PROGRESS.value: [
        ProjectStatus.QUALITY_CHECK.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.QUALITY_CHECK.value: [
        ProjectStatus.REVISIONS.value,
        ProjectStatus.READY_FOR_DELIVERY.value,
        ProjectStatus.COMPLETED.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.REVISIONS.value: [
        ProjectStatus.QUALITY_CHECK.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.READY_FOR_DELIVERY.value: [
        ProjectStatus.SHIPPED.value,
        ProjectStatus.DELIVERED.value,
        ProjectStatus.COMPLETED.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.SHIPPED.value: [
        ProjectStatus.DELIVERED.value,
        ProjectStatus.COMPLETED.value,
        ProjectStatus.ON_HOLD.value,
        ProjectStatus.CANCELLED.value,
    ],
    ProjectStatus.DELIVERED.value: [
        ProjectStatus.COMPLETED.value,
        ProjectStatus.REVISIONS.value,
    ],
    ProjectStatus.COMPLETED.value: [ProjectStatus.REVISIONS.value],
    ProjectStatus.ON_HOLD.value: [
        # Can resume to any previous state
        ProjectStatus.CONCEPT.value,
        ProjectStatus.PLANNING.value,
        ProjectStatus.DESIGN_PHASE.value,
        ProjectStatus.CLIENT_APPROVAL.value,
        ProjectStatus.MATERIAL_SELECTION.value,
        ProjectStatus.MATERIAL_PURCHASED.value,
        ProjectStatus.WAITING_FOR_MATERIALS.value,
        ProjectStatus.PRODUCTION_QUEUE.value,
        ProjectStatus.CUTTING.value,
        ProjectStatus.ASSEMBLY.value,
        ProjectStatus.STITCHING.value,
        ProjectStatus.EDGE_FINISHING.value,
        ProjectStatus.HARDWARE_INSTALLATION.value,
        ProjectStatus.IN_PROGRESS.value,
        ProjectStatus.QUALITY_CHECK.value,
        ProjectStatus.REVISIONS.value,
        ProjectStatus.READY_FOR_DELIVERY.value,
        ProjectStatus.CANCELLED.value,
    ],
}

# Status completion percentages to auto-set when changing status
STATUS_COMPLETION_PERCENTAGES = {
    ProjectStatus.CONCEPT.value: 0,
    ProjectStatus.PLANNING.value: 5,
    ProjectStatus.DESIGN_PHASE.value: 10,
    ProjectStatus.CLIENT_APPROVAL.value: 15,
    ProjectStatus.MATERIAL_SELECTION.value: 20,
    ProjectStatus.MATERIAL_PURCHASED.value: 25,
    ProjectStatus.WAITING_FOR_MATERIALS.value: 25,
    ProjectStatus.PRODUCTION_QUEUE.value: 30,
    ProjectStatus.CUTTING.value: 40,
    ProjectStatus.ASSEMBLY.value: 50,
    ProjectStatus.STITCHING.value: 60,
    ProjectStatus.EDGE_FINISHING.value: 70,
    ProjectStatus.HARDWARE_INSTALLATION.value: 80,
    ProjectStatus.IN_PROGRESS.value: 50,
    ProjectStatus.QUALITY_CHECK.value: 85,
    ProjectStatus.REVISIONS.value: 70,
    ProjectStatus.READY_FOR_DELIVERY.value: 90,
    ProjectStatus.SHIPPED.value: 95,
    ProjectStatus.DELIVERED.value: 98,
    ProjectStatus.COMPLETED.value: 100,
    ProjectStatus.ON_HOLD.value: None,  # Don't change percentage
    ProjectStatus.CANCELLED.value: None,  # Don't change percentage
}


class ProjectService(BaseService[Project]):
    """
    Service for managing projects in the HideSync system.

    Provides functionality for:
    - Project workflow management
    - Component and material tracking
    - Timeline and scheduling
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        material_service=None,
        timeline_task_repository=None,
        customer_repository=None,
    ):
        """
        Initialize ProjectService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            material_service: Optional material service for material operations
            timeline_task_repository: Optional timeline task repository
            customer_repository: Optional customer repository
        """
        self.session = session
        self.repository = repository or ProjectRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.material_service = material_service
        self.timeline_task_repository = (
            timeline_task_repository or TimelineTaskRepository(session)
        )
        self.customer_repository = customer_repository

    @validate_input(validate_project)
    def create_project(self, data: Dict[str, Any]) -> Project:
        """
        Create a new project.

        Args:
            data: Project data with required fields

        Returns:
            Created project entity

        Raises:
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Set default values if not provided
            if "start_date" not in data:
                data["start_date"] = datetime.now().date()

            if "status" not in data:
                data["status"] = ProjectStatus.PLANNING.value

            if "completion_percentage" not in data:
                suggested_percentage = STATUS_COMPLETION_PERCENTAGES.get(
                    data.get("status", ProjectStatus.PLANNING.value)
                )
                data["completion_percentage"] = (
                    suggested_percentage if suggested_percentage is not None else 0
                )

            # Create project
            project = self.repository.create(data)

            # Create default timeline tasks based on project type if needed
            if data.get("create_default_timeline", False):
                self._create_default_timeline_tasks(project)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProjectCreated(
                        project_id=project.id,
                        project_type=project.type,
                        customer_id=project.customer_id,
                        user_id=user_id,
                    )
                )

            return project

    def create_project_with_components(
        self, project_data: Dict[str, Any], components: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a new project with components.

        Args:
            project_data: Project data
            components: List of component data

        Returns:
            Created project with components

        Raises:
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Create project
            project = self.create_project(project_data)

            # Add components
            for component_data in components:
                self.add_component(project.id, component_data)

            return self.get_project_with_details(project.id)

    @validate_input(validate_project_component)
    def add_component(
        self, project_id: int, component_data: Dict[str, Any]
    ) -> ProjectComponent:
        """
        Add a component to a project.

        Args:
            project_id: Project ID
            component_data: Component data

        Returns:
            Created project component

        Raises:
            ProjectNotFoundException: If project not found
            ValidationException: If data validation fails
        """
        with self.transaction():
            project = self.repository.get_by_id(project_id)
            if not project:
                raise ProjectNotFoundException(project_id)

            component_data["project_id"] = project_id
            component = self.repository.add_component(component_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProjectComponentAdded(
                        project_id=project_id,
                        component_id=component.component_id,
                        quantity=component.quantity,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:{project_id}")

            return component

    def update_project_status(
        self,
        project_id: int,
        new_status: str,
        completion_percentage: Optional[float] = None,
        comments: Optional[str] = None,
    ) -> Project:
        """
        Update project status with audit trail.

        Args:
            project_id: Project ID
            new_status: New project status
            completion_percentage: Optional completion percentage
            comments: Optional status change comments

        Returns:
            Updated project

        Raises:
            ProjectNotFoundException: If project not found
            InvalidProjectStatusTransitionException: If status transition is invalid
        """
        with self.transaction():
            project = self.repository.get_by_id(project_id)
            if not project:
                raise ProjectNotFoundException(project_id)

            # Store previous status for event
            previous_status = project.status

            # Validate status transition
            if previous_status != new_status and not self._is_valid_status_transition(
                previous_status, new_status
            ):
                raise InvalidProjectStatusTransitionException(
                    project_id=project_id,
                    current_status=previous_status,
                    new_status=new_status,
                )

            # Prepare update data
            update_data = {"status": new_status}

            # Update completion percentage if provided or auto-set based on status
            if completion_percentage is not None:
                update_data["completion_percentage"] = min(
                    max(completion_percentage, 0), 100
                )
            elif STATUS_COMPLETION_PERCENTAGES.get(new_status) is not None:
                update_data["completion_percentage"] = STATUS_COMPLETION_PERCENTAGES[
                    new_status
                ]

            # Set completion for completed projects
            if new_status == ProjectStatus.COMPLETED.value:
                update_data["completion_percentage"] = 100
                update_data["completed_date"] = datetime.now().date()

            # Update project
            updated_project = self.repository.update(project_id, update_data)

            # Record status change in audit trail
            self._record_status_change(
                project_id=project_id,
                previous_status=previous_status,
                new_status=new_status,
                comments=comments,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProjectStatusChanged(
                        project_id=project_id,
                        previous_status=previous_status,
                        new_status=new_status,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:{project_id}")

            return updated_project

    def get_project_with_details(self, project_id: int) -> Dict[str, Any]:
        """
        Get project with comprehensive details for UI display.

        Args:
            project_id: Project ID

        Returns:
            Project with components, materials, and related entities

        Raises:
            ProjectNotFoundException: If project not found
        """
        project = self.repository.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        # Convert to dict and add related data
        result = (
            project.to_dict()
            if hasattr(project, "to_dict")
            else {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "type": project.type,
                "status": project.status,
                "start_date": (
                    project.start_date.isoformat() if project.start_date else None
                ),
                "due_date": project.due_date.isoformat() if project.due_date else None,
                "completed_date": (
                    project.completed_date.isoformat()
                    if project.completed_date
                    else None
                ),
                "completion_percentage": project.completion_percentage,
                "customer_id": project.customer_id,
                "template_id": project.template_id,
                "notes": project.notes,
            }
        )

        # Add components with their materials
        components = self.repository.get_project_components(project_id)
        result["components"] = [
            comp.to_dict() if hasattr(comp, "to_dict") else comp for comp in components
        ]

        # Add customer details if available
        if project.customer_id and self.customer_repository:
            customer = self.customer_repository.get_by_id(project.customer_id)
            if customer:
                result["customer"] = (
                    customer.to_dict()
                    if hasattr(customer, "to_dict")
                    else {
                        "id": customer.id,
                        "name": customer.name,
                        "email": customer.email,
                        "phone": customer.phone,
                    }
                )

        # Add material requirements
        result["material_requirements"] = self.calculate_material_requirements(
            project_id
        )

        # Add project timeline
        timeline_tasks = self.timeline_task_repository.find_by_project_id(project_id)
        result["timeline"] = [
            task.to_dict() if hasattr(task, "to_dict") else task
            for task in timeline_tasks
        ]

        # Add project status history
        result["status_history"] = self.repository.get_project_status_history(
            project_id
        )

        # Add next possible statuses
        result["possible_next_statuses"] = VALID_STATUS_TRANSITIONS.get(
            project.status, []
        )

        return result

    def get_projects_due_soon(self, days: int = 7) -> List[Project]:
        """
        Get projects due within the specified number of days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of projects due soon
        """
        today = datetime.now().date()
        due_date = today + timedelta(days=days)

        return self.repository.list(
            due_date_from=today,
            due_date_to=due_date,
            status_not=ProjectStatus.COMPLETED.value,
        )

    def calculate_material_requirements(
        self, project_id: int
    ) -> Dict[int, Dict[str, Any]]:
        """
        Calculate material requirements based on project components.

        Args:
            project_id: Project ID

        Returns:
            Dictionary of material requirements by material ID

        Raises:
            ProjectNotFoundException: If project not found
        """
        project = self.repository.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        # Get components with their materials
        components = self.repository.get_project_components_with_materials(project_id)

        # Aggregate material requirements
        requirements = {}

        for component in components:
            for material in component.materials:
                material_id = material.material_id

                if material_id not in requirements:
                    material_entity = None
                    if self.material_service:
                        try:
                            material_entity = self.material_service.get_by_id(
                                material_id
                            )
                        except MaterialNotFoundException:
                            pass

                    requirements[material_id] = {
                        "id": material_id,
                        "name": (
                            material_entity.name
                            if material_entity
                            else f"Material {material_id}"
                        ),
                        "quantity_required": 0,
                        "unit": (
                            material.unit
                            if hasattr(material, "unit")
                            else (material_entity.unit if material_entity else None)
                        ),
                        "available": material_entity.quantity if material_entity else 0,
                        "status": "unknown",
                    }

                # Add required quantity for this component
                quantity_required = material.quantity * component.quantity
                requirements[material_id]["quantity_required"] += quantity_required

                # Update status based on availability
                if "available" in requirements[material_id]:
                    available = requirements[material_id]["available"]
                    required = requirements[material_id]["quantity_required"]

                    if available >= required:
                        requirements[material_id]["status"] = "available"
                    elif available > 0:
                        requirements[material_id]["status"] = "partial"
                    else:
                        requirements[material_id]["status"] = "unavailable"

        return requirements

    def add_timeline_task(
        self, project_id: int, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a timeline task to a project.

        Args:
            project_id: Project ID
            task_data: Task data

        Returns:
            Created timeline task

        Raises:
            ProjectNotFoundException: If project not found
        """
        with self.transaction():
            project = self.repository.get_by_id(project_id)
            if not project:
                raise ProjectNotFoundException(project_id)

            # Add project ID to task data
            task_data["project_id"] = project_id

            # Set default start date if not provided
            if "start_date" not in task_data:
                task_data["start_date"] = datetime.now()

            # Create the task
            task = self.timeline_task_repository.create(task_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    TimelineTaskCreated(
                        task_id=task.id,
                        project_id=project_id,
                        task_name=task.name,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:{project_id}")

            return task

    def update_timeline_task(
        self, task_id: str, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a timeline task.

        Args:
            task_id: Task ID
            task_data: Updated task data

        Returns:
            Updated timeline task

        Raises:
            EntityNotFoundException: If task not found
        """
        with self.transaction():
            # Get the task for event creation and validation
            original_task = self.timeline_task_repository.get_by_id(task_id)
            if not original_task:
                raise EntityNotFoundException("TimelineTask", task_id)

            # Update the task
            updated_task = self.timeline_task_repository.update(task_id, task_data)

            # Publish event if event bus exists
            if self.event_bus:
                # Calculate changes
                changes = {}
                for key, new_value in task_data.items():
                    old_value = getattr(original_task, key, None)
                    if old_value != new_value:
                        changes[key] = {"old": old_value, "new": new_value}

                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    TimelineTaskUpdated(
                        task_id=task_id,
                        project_id=original_task.project_id,
                        changes=changes,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Project:{original_task.project_id}")

            return updated_task

    def delete_timeline_task(self, task_id: str) -> bool:
        """
        Delete a timeline task.

        Args:
            task_id: Task ID

        Returns:
            True if task was deleted, False otherwise
        """
        with self.transaction():
            # Get the task for event creation
            task = self.timeline_task_repository.get_by_id(task_id)
            if not task:
                return False

            project_id = task.project_id

            # Delete the task
            result = self.timeline_task_repository.delete(task_id)

            # Publish event if event bus exists and deletion succeeded
            if result and self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    TimelineTaskUpdated(
                        task_id=task_id,
                        project_id=project_id,
                        changes={"deleted": {"old": False, "new": True}},
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if result and self.cache_service:
                self.cache_service.invalidate(f"Project:{project_id}")

            return result

    def calculate_project_progress(self, project_id: int) -> float:
        """
        Calculate project progress based on timeline tasks and status.

        Args:
            project_id: Project ID

        Returns:
            Project progress percentage

        Raises:
            ProjectNotFoundException: If project not found
        """
        project = self.repository.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        # Get timeline tasks
        tasks = self.timeline_task_repository.find_by_project_id(project_id)

        if not tasks:
            # No tasks, use status-based percentage
            return STATUS_COMPLETION_PERCENTAGES.get(project.status, 0) or 0

        # Calculate progress based on task completion
        total_weight = 0
        weighted_progress = 0

        for task in tasks:
            # Default weight is 1 if not specified
            weight = getattr(task, "weight", 1) or 1
            progress = getattr(task, "progress", 0) or 0

            total_weight += weight
            weighted_progress += weight * progress

        if total_weight == 0:
            return 0

        progress_percentage = weighted_progress / total_weight

        # Update the project's completion percentage
        with self.transaction():
            self.repository.update(
                project_id, {"completion_percentage": progress_percentage}
            )

        return progress_percentage

    def get_project_timeline(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get timeline tasks for a project.

        Args:
            project_id: Project ID

        Returns:
            List of timeline tasks

        Raises:
            ProjectNotFoundException: If project not found
        """
        project = self.repository.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundException(project_id)

        tasks = self.timeline_task_repository.find_by_project_id(project_id)
        return [task.to_dict() if hasattr(task, "to_dict") else task for task in tasks]

    def _record_status_change(
        self,
        project_id: int,
        previous_status: str,
        new_status: str,
        comments: Optional[str] = None,
    ) -> None:
        """
        Record a status change in the project history.

        Args:
            project_id: Project ID
            previous_status: Previous status
            new_status: New status
            comments: Optional status change comments
        """
        # Implementation depends on project history model
        history_data = {
            "project_id": project_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "change_date": datetime.now(),
            "user_id": (
                self.security_context.current_user.id if self.security_context else None
            ),
            "comments": comments,
        }

        # Use repository to create history record
        self.repository.create_status_history(history_data)

    def _is_valid_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Check if a status transition is valid.

        Args:
            current_status: Current status
            new_status: New status

        Returns:
            True if transition is valid, False otherwise
        """
        # Same status is always valid
        if current_status == new_status:
            return True

        # Check valid transitions
        valid_transitions = VALID_STATUS_TRANSITIONS.get(current_status, [])
        return new_status in valid_transitions

    def _create_default_timeline_tasks(self, project: Project) -> None:
        """
        Create default timeline tasks based on project type.

        Args:
            project: Project to create tasks for
        """
        today = datetime.now().date()
        tasks = []

        # Common tasks for all project types
        tasks.append(
            {
                "project_id": project.id,
                "name": "Project Planning",
                "start_date": today,
                "end_date": today + timedelta(days=3),
                "progress": 0,
                "status": "pending",
                "is_critical_path": True,
            }
        )

        tasks.append(
            {
                "project_id": project.id,
                "name": "Material Selection",
                "start_date": today + timedelta(days=3),
                "end_date": today + timedelta(days=5),
                "progress": 0,
                "status": "pending",
                "is_critical_path": True,
            }
        )

        # Add type-specific tasks
        if project.type == ProjectType.WALLET.value:
            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Cutting Leather",
                    "start_date": today + timedelta(days=5),
                    "end_date": today + timedelta(days=6),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Assembly and Stitching",
                    "start_date": today + timedelta(days=6),
                    "end_date": today + timedelta(days=8),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

        elif (
            project.type == ProjectType.BAG.value
            or project.type == ProjectType.MESSENGER_BAG.value
        ):
            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Pattern Layout",
                    "start_date": today + timedelta(days=5),
                    "end_date": today + timedelta(days=6),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Cutting Leather",
                    "start_date": today + timedelta(days=6),
                    "end_date": today + timedelta(days=7),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Assembly",
                    "start_date": today + timedelta(days=7),
                    "end_date": today + timedelta(days=10),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Hardware Installation",
                    "start_date": today + timedelta(days=10),
                    "end_date": today + timedelta(days=11),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

        elif project.type == ProjectType.BELT.value:
            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Cutting Leather Strip",
                    "start_date": today + timedelta(days=5),
                    "end_date": today + timedelta(days=6),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Edge Finishing",
                    "start_date": today + timedelta(days=6),
                    "end_date": today + timedelta(days=7),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

            tasks.append(
                {
                    "project_id": project.id,
                    "name": "Buckle Installation",
                    "start_date": today + timedelta(days=7),
                    "end_date": today + timedelta(days=8),
                    "progress": 0,
                    "status": "pending",
                    "is_critical_path": True,
                }
            )

        # Common final tasks
        tasks.append(
            {
                "project_id": project.id,
                "name": "Quality Check",
                "start_date": today + timedelta(days=11),
                "end_date": today + timedelta(days=12),
                "progress": 0,
                "status": "pending",
                "is_critical_path": True,
            }
        )

        tasks.append(
            {
                "project_id": project.id,
                "name": "Final Finishing",
                "start_date": today + timedelta(days=12),
                "end_date": today + timedelta(days=13),
                "progress": 0,
                "status": "pending",
                "is_critical_path": True,
            }
        )

        # Create the tasks
        for task_data in tasks:
            self.timeline_task_repository.create(task_data)

    def _create_created_event(self, entity: Project) -> DomainEvent:
        """
        Create event for project creation.

        Args:
            entity: Created project entity

        Returns:
            ProjectCreated event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return ProjectCreated(
            project_id=entity.id,
            project_type=entity.type,
            customer_id=entity.customer_id,
            user_id=user_id,
        )

    def _create_updated_event(self, original: Project, updated: Project) -> DomainEvent:
        """
        Create event for project update.

        Args:
            original: Original project entity
            updated: Updated project entity

        Returns:
            ProjectUpdated event
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
        return ProjectUpdated(project_id=updated.id, changes=changes, user_id=user_id)

    def _create_deleted_event(self, entity: Project) -> DomainEvent:
        """
        Create event for project deletion.

        Args:
            entity: Deleted project entity

        Returns:
            ProjectDeleted event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return ProjectDeleted(project_id=entity.id, user_id=user_id)
