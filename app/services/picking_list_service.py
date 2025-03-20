# File: services/picking_list_service.py

"""
Picking list management service for the HideSync system.

This module provides comprehensive functionality for managing picking lists,
which represent material requisition documents for leathercraft projects.
It handles picking list creation, item management, status tracking, and
the coordination between projects, materials, and inventory.

Picking lists serve as a bridge between project planning and execution,
enabling craftspeople to prepare all necessary materials before starting work
and track material allocation throughout the production process.

Key features:
- Picking list creation from projects
- Item addition, removal, and quantity adjustment
- Status tracking through the fulfillment workflow
- Material reservation and allocation
- Integration with inventory management
- Item verification and quality control
- Reporting on material usage and availability

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with other
services like ProjectService, MaterialService, and InventoryService.
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
import logging
import json
import uuid
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentOperationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import PickingListStatus
from app.db.models.picking_list import PickingList, PickingListItem
from app.repositories.picking_list_repository import (
    PickingListRepository,
    PickingListItemRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class PickingListCreated(DomainEvent):
    """Event emitted when a picking list is created."""

    def __init__(
        self,
        picking_list_id: str,
        project_id: str,
        assigned_to: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize picking list created event.

        Args:
            picking_list_id: ID of the created picking list
            project_id: ID of the associated project
            assigned_to: Optional person assigned to the picking list
            user_id: Optional ID of the user who created the picking list
        """
        super().__init__()
        self.picking_list_id = picking_list_id
        self.project_id = project_id
        self.assigned_to = assigned_to
        self.user_id = user_id


class PickingListStatusChanged(DomainEvent):
    """Event emitted when a picking list's status changes."""

    def __init__(
        self,
        picking_list_id: str,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize picking list status changed event.

        Args:
            picking_list_id: ID of the picking list
            previous_status: Previous status
            new_status: New status
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.picking_list_id = picking_list_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


class PickingListItemAdded(DomainEvent):
    """Event emitted when an item is added to a picking list."""

    def __init__(
        self,
        picking_list_id: str,
        item_id: str,
        material_id: str,
        material_name: str,
        quantity: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize picking list item added event.

        Args:
            picking_list_id: ID of the picking list
            item_id: ID of the added item
            material_id: ID of the material
            material_name: Name of the material
            quantity: Quantity ordered
            user_id: Optional ID of the user who added the item
        """
        super().__init__()
        self.picking_list_id = picking_list_id
        self.item_id = item_id
        self.material_id = material_id
        self.material_name = material_name
        self.quantity = quantity
        self.user_id = user_id


class PickingListItemPicked(DomainEvent):
    """Event emitted when a picking list item is picked."""

    def __init__(
        self,
        picking_list_id: str,
        item_id: str,
        material_id: str,
        quantity_picked: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize picking list item picked event.

        Args:
            picking_list_id: ID of the picking list
            item_id: ID of the picked item
            material_id: ID of the material
            quantity_picked: Quantity picked
            user_id: Optional ID of the user who picked the item
        """
        super().__init__()
        self.picking_list_id = picking_list_id
        self.item_id = item_id
        self.material_id = material_id
        self.quantity_picked = quantity_picked
        self.user_id = user_id


class PickingListCompleted(DomainEvent):
    """Event emitted when a picking list is completed."""

    def __init__(
        self,
        picking_list_id: str,
        project_id: str,
        completed_by: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize picking list completed event.

        Args:
            picking_list_id: ID of the completed picking list
            project_id: ID of the associated project
            completed_by: Optional person who completed the picking list
            user_id: Optional ID of the user who marked the list as completed
        """
        super().__init__()
        self.picking_list_id = picking_list_id
        self.project_id = project_id
        self.completed_by = completed_by
        self.user_id = user_id


# Validation functions
validate_picking_list = validate_entity(PickingList)
validate_picking_list_item = validate_entity(PickingListItem)


class PickingListService(BaseService[PickingList]):
    """
    Service for managing picking lists in the HideSync system.

    Provides functionality for:
    - Picking list creation and management
    - Item tracking and fulfillment
    - Material allocation for projects
    - Status workflow management
    - Integration with inventory and materials
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        item_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        project_service=None,
        material_service=None,
        inventory_service=None,
        component_service=None,
    ):
        """
        Initialize PickingListService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for picking lists
            item_repository: Optional repository for picking list items
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            project_service: Optional service for project operations
            material_service: Optional service for material operations
            inventory_service: Optional service for inventory operations
            component_service: Optional service for component operations
        """
        self.session = session
        self.repository = repository or PickingListRepository(session)
        self.item_repository = item_repository or PickingListItemRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.project_service = project_service
        self.material_service = material_service
        self.inventory_service = inventory_service
        self.component_service = component_service

    @validate_input(validate_picking_list)
    def create_picking_list(self, data: Dict[str, Any]) -> PickingList:
        """
        Create a new picking list.

        Args:
            data: Picking list data with required fields
                Required fields:
                - project_id: ID of the project this list is for
                Optional fields:
                - status: Initial status (defaults to PENDING)
                - assignedTo: Person assigned to pick the list
                - notes: Additional notes or instructions
                - items: List of initial items to add

        Returns:
            Created picking list entity

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If referenced project not found
        """
        with self.transaction():
            # Check if project exists if project service is available
            project_id = data.get("project_id")
            if project_id and self.project_service:
                project = self.project_service.get_by_id(project_id)
                if not project:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Project", project_id)

            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set default values if not provided
            if "status" not in data:
                data["status"] = PickingListStatus.PENDING.value

            if "createdAt" not in data:
                data["createdAt"] = datetime.now()

            # Extract items for later creation
            items = data.pop("items", [])

            # Create picking list
            picking_list = self.repository.create(data)

            # Add initial items if provided
            for item_data in items:
                item_data["picking_list_id"] = picking_list.id
                self.add_item(picking_list.id, item_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PickingListCreated(
                        picking_list_id=picking_list.id,
                        project_id=project_id,
                        assigned_to=data.get("assignedTo"),
                        user_id=user_id,
                    )
                )

            return picking_list

    def create_picking_list_from_project(
        self,
        project_id: str,
        assigned_to: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PickingList:
        """
        Create a picking list automatically from a project and its material requirements.

        Args:
            project_id: ID of the project
            assigned_to: Optional person assigned to pick the list
            notes: Optional additional notes

        Returns:
            Created picking list entity with items

        Raises:
            EntityNotFoundException: If project not found
        """
        with self.transaction():
            # Check if project exists if project service is available
            if self.project_service:
                project = self.project_service.get_by_id(project_id)
                if not project:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Project", project_id)

                # Create base picking list
                picking_list_data = {
                    "project_id": project_id,
                    "status": PickingListStatus.PENDING.value,
                    "assignedTo": assigned_to,
                    "notes": (
                        notes or f"Automatically generated for {project.name}"
                        if hasattr(project, "name")
                        else "Automatically generated"
                    ),
                }

                picking_list = self.create_picking_list(picking_list_data)

                # Get material requirements if pattern and component services are available
                if (
                    self.component_service
                    and hasattr(project, "patternId")
                    and project.patternId
                ):
                    try:
                        # Get material requirements
                        requirements = (
                            self.component_service.calculate_material_requirements(
                                project.patternId
                            )
                        )

                        # Add each material as an item
                        for material_id, material_data in requirements.items():
                            # Create item
                            item_data = {
                                "material_id": material_id,
                                "quantity_ordered": material_data.get(
                                    "quantity_required", 0
                                ),
                                "status": "pending",
                            }

                            # Add component reference if available
                            component_id = None
                            if (
                                "components" in material_data
                                and material_data["components"]
                            ):
                                # Just use the first component reference for simplicity
                                # In a full implementation, we might want to track all components
                                component_id = material_data["components"][0].get(
                                    "component_id"
                                )

                            if component_id:
                                item_data["component_id"] = component_id

                            # Add item to picking list
                            self.add_item(picking_list.id, item_data)

                    except Exception as e:
                        logger.warning(
                            f"Failed to calculate material requirements for project: {str(e)}"
                        )

                return picking_list
            else:
                # Without project service, we can't validate or get materials
                # Just create a basic picking list
                picking_list_data = {
                    "project_id": project_id,
                    "status": PickingListStatus.PENDING.value,
                    "assignedTo": assigned_to,
                    "notes": notes or "Automatically generated",
                }

                return self.create_picking_list(picking_list_data)

    def update_picking_list(
        self, picking_list_id: str, data: Dict[str, Any]
    ) -> PickingList:
        """
        Update an existing picking list.

        Args:
            picking_list_id: ID of the picking list to update
            data: Updated picking list data

        Returns:
            Updated picking list entity

        Raises:
            EntityNotFoundException: If picking list not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if picking list exists
            picking_list = self.get_by_id(picking_list_id)
            if not picking_list:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingList", picking_list_id)

            # Check if status is changing
            previous_status = (
                picking_list.status if hasattr(picking_list, "status") else None
            )
            new_status = data.get("status")

            # Validate status transition if status is changing
            if new_status and previous_status and new_status != previous_status:
                self._validate_status_transition(previous_status, new_status)

                # Set completion timestamp if being marked as completed
                if new_status == PickingListStatus.COMPLETED.value:
                    data["completedAt"] = datetime.now()

            # Update picking list
            updated_list = self.repository.update(picking_list_id, data)

            # Publish status change event if status changed
            if (
                new_status
                and previous_status
                and new_status != previous_status
                and self.event_bus
            ):
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PickingListStatusChanged(
                        picking_list_id=picking_list_id,
                        previous_status=previous_status,
                        new_status=new_status,
                        user_id=user_id,
                    )
                )

                # If status changed to completed, publish completed event
                if new_status == PickingListStatus.COMPLETED.value:
                    self.event_bus.publish(
                        PickingListCompleted(
                            picking_list_id=picking_list_id,
                            project_id=updated_list.project_id,
                            completed_by=(
                                updated_list.assignedTo
                                if hasattr(updated_list, "assignedTo")
                                else None
                            ),
                            user_id=user_id,
                        )
                    )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PickingList:{picking_list_id}")
                self.cache_service.invalidate(f"PickingList:detail:{picking_list_id}")

            return updated_list

    def update_status(
        self, picking_list_id: str, status: Union[PickingListStatus, str]
    ) -> PickingList:
        """
        Update the status of a picking list.

        Args:
            picking_list_id: ID of the picking list
            status: New status value

        Returns:
            Updated picking list entity

        Raises:
            EntityNotFoundException: If picking list not found
            ValidationException: If status transition is invalid
        """
        # Convert string status to enum if needed
        if isinstance(status, str):
            try:
                status = PickingListStatus[status.upper()]
                status = status.value
            except (KeyError, AttributeError):
                # Keep as is if not a valid enum name
                pass

        return self.update_picking_list(picking_list_id, {"status": status})

    def get_picking_list_with_details(self, picking_list_id: str) -> Dict[str, Any]:
        """
        Get a picking list with comprehensive details.

        Args:
            picking_list_id: ID of the picking list

        Returns:
            Picking list with items and related details

        Raises:
            EntityNotFoundException: If picking list not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"PickingList:detail:{picking_list_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get picking list
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PickingList", picking_list_id)

        # Convert to dict
        result = picking_list.to_dict()

        # Get project details if available
        project_id = picking_list.project_id
        if project_id and self.project_service:
            try:
                project = self.project_service.get_by_id(project_id)
                if project:
                    result["project"] = {
                        "id": project.id,
                        "name": project.name if hasattr(project, "name") else None,
                        "type": project.type if hasattr(project, "type") else None,
                        "status": (
                            project.status if hasattr(project, "status") else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"Failed to get project for picking list: {str(e)}")

        # Get items with details
        items = self.get_items(picking_list_id)
        result["items"] = items

        # Calculate completion statistics
        total_items = len(items)
        completed_items = sum(1 for item in items if item.get("status") == "complete")
        partial_items = sum(1 for item in items if item.get("status") == "partial")

        result["completion_stats"] = {
            "total_items": total_items,
            "completed_items": completed_items,
            "partial_items": partial_items,
            "pending_items": total_items - completed_items - partial_items,
            "completion_percentage": (
                (completed_items / total_items * 100) if total_items > 0 else 0
            ),
        }

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    @validate_input(validate_picking_list_item)
    def add_item(self, picking_list_id: str, data: Dict[str, Any]) -> PickingListItem:
        """
        Add an item to a picking list.

        Args:
            picking_list_id: ID of the picking list
            data: Item data with required fields
                Required fields:
                - material_id: ID of the material
                - quantity_ordered: Quantity needed
                Optional fields:
                - component_id: ID of the associated component
                - status: Item status (defaults to "pending")
                - notes: Additional notes

        Returns:
            Created picking list item entity

        Raises:
            EntityNotFoundException: If picking list not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if picking list exists
            picking_list = self.get_by_id(picking_list_id)
            if not picking_list:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingList", picking_list_id)

            # Set picking list ID
            data["picking_list_id"] = picking_list_id

            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set default values if not provided
            if "status" not in data:
                data["status"] = "pending"

            if "quantity_picked" not in data:
                data["quantity_picked"] = 0

            # Check if material exists and get name if material service is available
            material_id = data.get("material_id")
            material_name = None
            if material_id and self.material_service:
                material = self.material_service.get_by_id(material_id)
                if not material:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Material", material_id)

                material_name = (
                    material.name
                    if hasattr(material, "name")
                    else f"Material {material_id}"
                )

            # Check if component exists if component ID is provided and component service is available
            component_id = data.get("component_id")
            if component_id and self.component_service:
                component = self.component_service.get_by_id(component_id)
                if not component:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Component", component_id)

            # Create item
            item = self.item_repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PickingListItemAdded(
                        picking_list_id=picking_list_id,
                        item_id=item.id,
                        material_id=material_id,
                        material_name=material_name or f"Material {material_id}",
                        quantity=data.get("quantity_ordered", 0),
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PickingList:detail:{picking_list_id}")

            return item

    def update_item(self, item_id: str, data: Dict[str, Any]) -> PickingListItem:
        """
        Update a picking list item.

        Args:
            item_id: ID of the item to update
            data: Updated item data

        Returns:
            Updated picking list item entity

        Raises:
            EntityNotFoundException: If item not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if item exists
            item = self.item_repository.get_by_id(item_id)
            if not item:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingListItem", item_id)

            # Store original values for event
            original_quantity_picked = (
                item.quantity_picked if hasattr(item, "quantity_picked") else 0
            )
            picking_list_id = item.picking_list_id
            material_id = item.material_id

            # Check if quantity picked is changing
            new_quantity_picked = data.get("quantity_picked")

            # Update item
            updated_item = self.item_repository.update(item_id, data)

            # Update item status based on quantities if not explicitly provided
            if "status" not in data and new_quantity_picked is not None:
                quantity_ordered = (
                    updated_item.quantity_ordered
                    if hasattr(updated_item, "quantity_ordered")
                    else 0
                )
                if new_quantity_picked >= quantity_ordered:
                    self.item_repository.update(item_id, {"status": "complete"})
                elif new_quantity_picked > 0:
                    self.item_repository.update(item_id, {"status": "partial"})
                else:
                    self.item_repository.update(item_id, {"status": "pending"})

            # Publish event if quantity picked changed and event bus exists
            if (
                new_quantity_picked is not None
                and new_quantity_picked != original_quantity_picked
                and self.event_bus
            ):
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )

                # Calculate quantity difference for inventory adjustment
                quantity_difference = new_quantity_picked - original_quantity_picked

                # Only emit event if there's a positive change
                if quantity_difference > 0:
                    self.event_bus.publish(
                        PickingListItemPicked(
                            picking_list_id=picking_list_id,
                            item_id=item_id,
                            material_id=material_id,
                            quantity_picked=quantity_difference,  # Only the newly picked amount
                            user_id=user_id,
                        )
                    )

                    # Adjust inventory if inventory service is available
                    if self.inventory_service and quantity_difference > 0:
                        self.inventory_service.adjust_inventory(
                            item_type="material",
                            item_id=material_id,
                            quantity_change=-quantity_difference,  # Negative because we're removing from inventory
                            adjustment_type="PROJECT_USAGE",
                            reason=(
                                f"Picked for project {updated_item.picking_list.project_id}"
                                if hasattr(updated_item, "picking_list")
                                and hasattr(updated_item.picking_list, "project_id")
                                else "Picked for project"
                            ),
                            reference_id=picking_list_id,
                        )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PickingList:detail:{picking_list_id}")

            return updated_item

    def pick_item(
        self,
        item_id: str,
        quantity_picked: float,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PickingListItem:
        """
        Mark an item as picked (fully or partially).

        Args:
            item_id: ID of the item
            quantity_picked: Quantity picked
            location: Optional storage location where item was picked from
            notes: Optional notes about the picking

        Returns:
            Updated picking list item entity

        Raises:
            EntityNotFoundException: If item not found
            ValidationException: If quantity is invalid
        """
        with self.transaction():
            # Check if item exists
            item = self.item_repository.get_by_id(item_id)
            if not item:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingListItem", item_id)

            # Validate quantity
            if quantity_picked <= 0:
                raise ValidationException(
                    "Picked quantity must be greater than zero",
                    {"quantity_picked": ["Must be greater than zero"]},
                )

            # Calculate new picked quantity
            current_picked = (
                item.quantity_picked if hasattr(item, "quantity_picked") else 0
            )
            new_picked = current_picked + quantity_picked

            # Determine status based on quantities
            quantity_ordered = (
                item.quantity_ordered if hasattr(item, "quantity_ordered") else 0
            )
            if new_picked >= quantity_ordered:
                status = "complete"
            else:
                status = "partial"

            # Update item
            update_data = {"quantity_picked": new_picked, "status": status}

            # Add location and notes if provided
            if location:
                update_data["location"] = location

            if notes:
                # Append to existing notes if any
                existing_notes = (
                    item.notes if hasattr(item, "notes") and item.notes else ""
                )
                if existing_notes:
                    update_data["notes"] = f"{existing_notes}\n{notes}"
                else:
                    update_data["notes"] = notes

            return self.update_item(item_id, update_data)

    def delete_item(self, item_id: str) -> bool:
        """
        Remove an item from a picking list.

        Args:
            item_id: ID of the item to remove

        Returns:
            True if removal was successful

        Raises:
            EntityNotFoundException: If item not found
            BusinessRuleException: If item has already been picked
        """
        with self.transaction():
            # Check if item exists
            item = self.item_repository.get_by_id(item_id)
            if not item:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingListItem", item_id)

            # Check if item has been picked
            if (hasattr(item, "quantity_picked") and item.quantity_picked > 0) or (
                hasattr(item, "status") and item.status in ["partial", "complete"]
            ):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot delete an item that has already been picked",
                    "PICKING_LIST_001",
                )

            # Store picking list ID for cache invalidation
            picking_list_id = item.picking_list_id

            # Delete item
            result = self.item_repository.delete(item_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"PickingList:detail:{picking_list_id}")

            return result

    def get_items(self, picking_list_id: str) -> List[Dict[str, Any]]:
        """
        Get all items for a picking list with detailed information.

        Args:
            picking_list_id: ID of the picking list

        Returns:
            List of items with detailed information
        """
        # Get items
        items = self.item_repository.list(picking_list_id=picking_list_id)

        result = []
        for item in items:
            item_dict = item.to_dict()

            # Add material details if material service is available
            material_id = item_dict.get("material_id")
            if material_id and self.material_service:
                try:
                    material = self.material_service.get_by_id(material_id)
                    if material:
                        item_dict["material"] = {
                            "id": material.id,
                            "name": (
                                material.name if hasattr(material, "name") else None
                            ),
                            "materialType": (
                                material.materialType
                                if hasattr(material, "materialType")
                                else None
                            ),
                            "unit": (
                                material.unit if hasattr(material, "unit") else None
                            ),
                            "status": (
                                material.status if hasattr(material, "status") else None
                            ),
                            "storageLocation": (
                                material.storageLocation
                                if hasattr(material, "storageLocation")
                                else None
                            ),
                        }
                except Exception as e:
                    logger.warning(f"Failed to get material for item: {str(e)}")

            # Add component details if component service is available
            component_id = item_dict.get("component_id")
            if component_id and self.component_service:
                try:
                    component = self.component_service.get_by_id(component_id)
                    if component:
                        item_dict["component"] = {
                            "id": component.id,
                            "name": (
                                component.name if hasattr(component, "name") else None
                            ),
                            "componentType": (
                                component.componentType
                                if hasattr(component, "componentType")
                                else None
                            ),
                        }
                except Exception as e:
                    logger.warning(f"Failed to get component for item: {str(e)}")

            # Add completion percentage
            quantity_ordered = item_dict.get("quantity_ordered", 0)
            quantity_picked = item_dict.get("quantity_picked", 0)
            if quantity_ordered > 0:
                item_dict["completion_percentage"] = min(
                    100, round(quantity_picked / quantity_ordered * 100, 1)
                )
            else:
                item_dict["completion_percentage"] = 0

            result.append(item_dict)

        return result

    def get_picking_lists_by_project(self, project_id: str) -> List[PickingList]:
        """
        Get all picking lists for a specific project.

        Args:
            project_id: ID of the project

        Returns:
            List of picking lists for the project
        """
        return self.repository.list(project_id=project_id)

    def get_active_picking_lists(self) -> List[PickingList]:
        """
        Get all active (pending or in-progress) picking lists.

        Returns:
            List of active picking lists
        """
        return self.repository.list_active()

    def get_incomplete_items(self, picking_list_id: str) -> List[Dict[str, Any]]:
        """
        Get items that haven't been fully picked yet.

        Args:
            picking_list_id: ID of the picking list

        Returns:
            List of incomplete items

        Raises:
            EntityNotFoundException: If picking list not found
        """
        # Check if picking list exists
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PickingList", picking_list_id)

        # Get all items
        all_items = self.get_items(picking_list_id)

        # Filter for incomplete items
        return [
            item for item in all_items if item.get("status") in ["pending", "partial"]
        ]

    def check_list_completion(self, picking_list_id: str) -> bool:
        """
        Check if all items in a picking list have been picked.

        Args:
            picking_list_id: ID of the picking list

        Returns:
            True if all items are complete, False otherwise

        Raises:
            EntityNotFoundException: If picking list not found
        """
        # Check if picking list exists
        picking_list = self.get_by_id(picking_list_id)
        if not picking_list:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("PickingList", picking_list_id)

        # Get incomplete items
        incomplete = self.get_incomplete_items(picking_list_id)

        # If no incomplete items and list is not already completed, update status
        if not incomplete and picking_list.status != PickingListStatus.COMPLETED.value:
            self.update_status(picking_list_id, PickingListStatus.COMPLETED)
            return True

        return not incomplete

    def mark_list_completed(
        self,
        picking_list_id: str,
        completed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PickingList:
        """
        Mark a picking list as completed, regardless of item status.

        Args:
            picking_list_id: ID of the picking list
            completed_by: Optional name of person completing the list
            notes: Optional completion notes

        Returns:
            Updated picking list entity

        Raises:
            EntityNotFoundException: If picking list not found
        """
        with self.transaction():
            # Check if picking list exists
            picking_list = self.get_by_id(picking_list_id)
            if not picking_list:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingList", picking_list_id)

            # Prepare update data
            update_data = {
                "status": PickingListStatus.COMPLETED.value,
                "completedAt": datetime.now(),
            }

            if completed_by:
                update_data["assignedTo"] = completed_by

            if notes:
                # Append to existing notes if any
                existing_notes = (
                    picking_list.notes
                    if hasattr(picking_list, "notes") and picking_list.notes
                    else ""
                )
                if existing_notes:
                    update_data["notes"] = (
                        f"{existing_notes}\nCompletion notes: {notes}"
                    )
                else:
                    update_data["notes"] = f"Completion notes: {notes}"

            # Update list
            return self.update_picking_list(picking_list_id, update_data)

    def cancel_picking_list(self, picking_list_id: str, reason: str) -> PickingList:
        """
        Cancel a picking list.

        Args:
            picking_list_id: ID of the picking list
            reason: Reason for cancellation

        Returns:
            Updated picking list entity

        Raises:
            EntityNotFoundException: If picking list not found
            BusinessRuleException: If list is already completed
        """
        with self.transaction():
            # Check if picking list exists
            picking_list = self.get_by_id(picking_list_id)
            if not picking_list:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("PickingList", picking_list_id)

            # Check if list is already completed
            if picking_list.status == PickingListStatus.COMPLETED.value:
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot cancel a completed picking list", "PICKING_LIST_002"
                )

            # Prepare update data
            update_data = {"status": PickingListStatus.CANCELLED.value}

            # Append cancellation reason to notes
            existing_notes = (
                picking_list.notes
                if hasattr(picking_list, "notes") and picking_list.notes
                else ""
            )
            if existing_notes:
                update_data["notes"] = (
                    f"{existing_notes}\nCancellation reason: {reason}"
                )
            else:
                update_data["notes"] = f"Cancellation reason: {reason}"

            # Update list
            return self.update_picking_list(picking_list_id, update_data)

    def generate_picking_list_report(self, picking_list_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive report for a picking list.

        Args:
            picking_list_id: ID of the picking list

        Returns:
            Dictionary with report data

        Raises:
            EntityNotFoundException: If picking list not found
        """
        # Get picking list with details
        picking_list = self.get_picking_list_with_details(picking_list_id)

        # Calculate statistics
        items = picking_list.get("items", [])
        total_items = len(items)
        completed_items = sum(1 for item in items if item.get("status") == "complete")
        partial_items = sum(1 for item in items if item.get("status") == "partial")
        pending_items = total_items - completed_items - partial_items

        # Calculate quantities
        total_ordered = sum(item.get("quantity_ordered", 0) for item in items)
        total_picked = sum(item.get("quantity_picked", 0) for item in items)

        # Group by material type if available
        material_types = {}
        material_locations = {}

        for item in items:
            material = item.get("material", {})
            material_type = material.get("materialType")

            if material_type:
                if material_type not in material_types:
                    material_types[material_type] = {
                        "count": 0,
                        "quantity_ordered": 0,
                        "quantity_picked": 0,
                    }

                material_types[material_type]["count"] += 1
                material_types[material_type]["quantity_ordered"] += item.get(
                    "quantity_ordered", 0
                )
                material_types[material_type]["quantity_picked"] += item.get(
                    "quantity_picked", 0
                )

            # Track storage locations
            location = material.get("storageLocation")
            if location:
                if location not in material_locations:
                    material_locations[location] = {
                        "count": 0,
                        "quantity_ordered": 0,
                        "quantity_picked": 0,
                    }

                material_locations[location]["count"] += 1
                material_locations[location]["quantity_ordered"] += item.get(
                    "quantity_ordered", 0
                )
                material_locations[location]["quantity_picked"] += item.get(
                    "quantity_picked", 0
                )

        # Build report
        report = {
            "picking_list_id": picking_list_id,
            "project_id": picking_list.get("project_id"),
            "project_name": picking_list.get("project", {}).get("name"),
            "status": picking_list.get("status"),
            "created_at": picking_list.get("createdAt"),
            "completed_at": picking_list.get("completedAt"),
            "assigned_to": picking_list.get("assignedTo"),
            "statistics": {
                "total_items": total_items,
                "completed_items": completed_items,
                "partial_items": partial_items,
                "pending_items": pending_items,
                "completion_percentage": (
                    (completed_items / total_items * 100) if total_items > 0 else 0
                ),
                "total_ordered": total_ordered,
                "total_picked": total_picked,
                "picking_percentage": (
                    (total_picked / total_ordered * 100) if total_ordered > 0 else 0
                ),
            },
            "by_material_type": material_types,
            "by_location": material_locations,
            "items": items,
        }

        return report

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """
        Validate that a status transition is allowed based on business rules.

        Args:
            current_status: Current status
            new_status: Proposed new status

        Raises:
            ValidationException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            PickingListStatus.PENDING.value: [
                PickingListStatus.IN_PROGRESS.value,
                PickingListStatus.CANCELLED.value,
            ],
            PickingListStatus.IN_PROGRESS.value: [
                PickingListStatus.COMPLETED.value,
                PickingListStatus.CANCELLED.value,
            ],
            PickingListStatus.COMPLETED.value: [
                # Generally can't transition from completed, but could add exceptions
            ],
            PickingListStatus.CANCELLED.value: [
                # Generally can't transition from cancelled, but could add exceptions
                PickingListStatus.PENDING.value
            ],
        }

        # Allow transition to same status
        if current_status == new_status:
            return

        # Check if transition is allowed
        if new_status not in allowed_transitions.get(current_status, []):
            allowed = allowed_transitions.get(current_status, [])
            allowed_names = [s for s in allowed]

            raise ValidationException(
                f"Cannot transition from {current_status} to {new_status}",
                {
                    "status": [
                        f"Invalid transition. Allowed transitions: {', '.join(allowed_names)}"
                    ]
                },
            )
