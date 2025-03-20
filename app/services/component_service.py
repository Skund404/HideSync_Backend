# File: services/component_service.py

"""
Component management service for the HideSync system.

This module provides comprehensive functionality for managing leathercraft components,
which are the building blocks of patterns and projects. It handles component creation,
material requirements, positioning, and the relationships between components and patterns.

Components represent discrete elements of a leathercraft project such as panels, pockets,
straps, and decorative elements, each with specific material requirements, dimensions,
and positions within a pattern.

Key features:
- Component creation and management
- Material requirement specification
- Component positioning and attributes
- Relationship management with patterns and projects
- Component cloning and modification
- Component search and categorization

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with other
services like MaterialService for material requirements management.
"""

from typing import List, Optional, Dict, Any, Union
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
from app.db.models.enums import ComponentType, MaterialType, MeasurementUnit
from app.db.models.component import Component, ComponentMaterial
from app.repositories.component_repository import (
    ComponentRepository,
    ComponentMaterialRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ComponentCreated(DomainEvent):
    """Event emitted when a component is created."""

    def __init__(
        self,
        component_id: int,
        name: str,
        component_type: str,
        pattern_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize component created event.

        Args:
            component_id: ID of the created component
            name: Name of the component
            component_type: Type of component
            pattern_id: Optional ID of the parent pattern
            user_id: Optional ID of the user who created the component
        """
        super().__init__()
        self.component_id = component_id
        self.name = name
        self.component_type = component_type
        self.pattern_id = pattern_id
        self.user_id = user_id


class ComponentUpdated(DomainEvent):
    """Event emitted when a component is updated."""

    def __init__(
        self,
        component_id: int,
        name: str,
        component_type: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize component updated event.

        Args:
            component_id: ID of the updated component
            name: Name of the component
            component_type: Type of component
            user_id: Optional ID of the user who updated the component
        """
        super().__init__()
        self.component_id = component_id
        self.name = name
        self.component_type = component_type
        self.user_id = user_id


class ComponentDeleted(DomainEvent):
    """Event emitted when a component is deleted."""

    def __init__(self, component_id: int, name: str, user_id: Optional[int] = None):
        """
        Initialize component deleted event.

        Args:
            component_id: ID of the deleted component
            name: Name of the component
            user_id: Optional ID of the user who deleted the component
        """
        super().__init__()
        self.component_id = component_id
        self.name = name
        self.user_id = user_id


class MaterialRequirementAdded(DomainEvent):
    """Event emitted when a material requirement is added to a component."""

    def __init__(
        self,
        component_id: int,
        material_id: int,
        material_type: str,
        quantity: float,
        unit: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize material requirement added event.

        Args:
            component_id: ID of the component
            material_id: ID of the material
            material_type: Type of material
            quantity: Required quantity
            unit: Measurement unit
            user_id: Optional ID of the user who added the requirement
        """
        super().__init__()
        self.component_id = component_id
        self.material_id = material_id
        self.material_type = material_type
        self.quantity = quantity
        self.unit = unit
        self.user_id = user_id


class MaterialRequirementRemoved(DomainEvent):
    """Event emitted when a material requirement is removed from a component."""

    def __init__(
        self, component_id: int, material_id: int, user_id: Optional[int] = None
    ):
        """
        Initialize material requirement removed event.

        Args:
            component_id: ID of the component
            material_id: ID of the material
            user_id: Optional ID of the user who removed the requirement
        """
        super().__init__()
        self.component_id = component_id
        self.material_id = material_id
        self.user_id = user_id


# Validation functions
validate_component = validate_entity(Component)
validate_component_material = validate_entity(ComponentMaterial)


class ComponentService(BaseService[Component]):
    """
    Service for managing components in the HideSync system.

    Provides functionality for:
    - Component creation and management
    - Material requirement specification
    - Component positioning and attributes
    - Component duplication and modification
    - Relationship management with patterns and projects
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        material_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        material_service=None,
        pattern_service=None,
    ):
        """
        Initialize ComponentService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for components
            material_repository: Optional repository for component materials
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            material_service: Optional service for material operations
            pattern_service: Optional service for pattern operations
        """
        self.session = session
        self.repository = repository or ComponentRepository(session)
        self.material_repository = material_repository or ComponentMaterialRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.material_service = material_service
        self.pattern_service = pattern_service

    @validate_input(validate_component)
    def create_component(self, data: Dict[str, Any]) -> Component:
        """
        Create a new component.

        Args:
            data: Component data with required fields
                Required fields:
                - name: Component name
                - componentType: Type of component
                Optional fields:
                - patternId: ID of the parent pattern
                - description: Component description
                - attributes: Additional component attributes (JSON)
                - pathData: SVG path data for component shape
                - position: Position data (JSON)
                - rotation: Rotation in degrees
                - isOptional: Whether component is optional in projects

        Returns:
            Created component entity

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If referenced pattern not found
        """
        with self.transaction():
            # Check if pattern exists if pattern ID is provided
            pattern_id = data.get("patternId")
            if pattern_id and self.pattern_service:
                pattern = self.pattern_service.get_by_id(pattern_id)
                if not pattern:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Pattern", pattern_id)

            # Set default values if not provided
            if "isOptional" not in data:
                data["isOptional"] = False

            if "createdAt" not in data:
                data["createdAt"] = datetime.now()

            if "modifiedAt" not in data:
                data["modifiedAt"] = datetime.now()

            if "rotation" not in data:
                data["rotation"] = 0

            # Convert JSON fields to strings if they're dictionaries
            if "attributes" in data and isinstance(data["attributes"], dict):
                data["attributes"] = json.dumps(data["attributes"])

            if "position" in data and isinstance(data["position"], dict):
                data["position"] = json.dumps(data["position"])

            # Create component
            component = self.repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ComponentCreated(
                        component_id=component.id,
                        name=component.name,
                        component_type=component.componentType,
                        pattern_id=pattern_id,
                        user_id=user_id,
                    )
                )

            return component

    def update_component(self, component_id: int, data: Dict[str, Any]) -> Component:
        """
        Update an existing component.

        Args:
            component_id: ID of the component to update
            data: Updated component data

        Returns:
            Updated component entity

        Raises:
            EntityNotFoundException: If component not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if component exists
            component = self.get_by_id(component_id)
            if not component:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Component", component_id)

            # Update modification time
            data["modifiedAt"] = datetime.now()

            # Convert JSON fields to strings if they're dictionaries
            if "attributes" in data and isinstance(data["attributes"], dict):
                data["attributes"] = json.dumps(data["attributes"])

            if "position" in data and isinstance(data["position"], dict):
                data["position"] = json.dumps(data["position"])

            # Update component
            updated_component = self.repository.update(component_id, data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ComponentUpdated(
                        component_id=component_id,
                        name=updated_component.name,
                        component_type=updated_component.componentType,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Component:{component_id}")
                self.cache_service.invalidate(f"Component:detail:{component_id}")

            return updated_component

    def delete_component(self, component_id: int) -> bool:
        """
        Delete a component.

        Args:
            component_id: ID of the component to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If component not found
            BusinessRuleException: If component is in use by projects
        """
        with self.transaction():
            # Check if component exists
            component = self.get_by_id(component_id)
            if not component:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Component", component_id)

            # Check if component is in use by projects
            if self._is_component_in_use(component_id):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot delete component that is in use by projects",
                    "COMPONENT_001",
                )

            # Store component name for event
            component_name = component.name

            # Delete material requirements first
            self._delete_component_materials(component_id)

            # Delete component
            result = self.repository.delete(component_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ComponentDeleted(
                        component_id=component_id, name=component_name, user_id=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Component:{component_id}")
                self.cache_service.invalidate(f"Component:detail:{component_id}")

            return result

    def get_component_with_details(self, component_id: int) -> Dict[str, Any]:
        """
        Get a component with comprehensive details including material requirements.

        Args:
            component_id: ID of the component

        Returns:
            Component with material requirement details

        Raises:
            EntityNotFoundException: If component not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Component:detail:{component_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get component
        component = self.get_by_id(component_id)
        if not component:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Component", component_id)

        # Convert to dict
        result = component.to_dict()

        # Parse JSON fields
        if "attributes" in result and result["attributes"]:
            try:
                result["attributes"] = json.loads(result["attributes"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is
                pass

        if "position" in result and result["position"]:
            try:
                result["position"] = json.loads(result["position"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is
                pass

        # Get pattern details if available
        pattern_id = result.get("patternId")
        if pattern_id and self.pattern_service:
            try:
                pattern = self.pattern_service.get_by_id(pattern_id)
                if pattern:
                    result["pattern"] = {
                        "id": pattern.id,
                        "name": pattern.name,
                        "projectType": (
                            pattern.projectType
                            if hasattr(pattern, "projectType")
                            else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"Failed to get pattern for component: {str(e)}")

        # Get material requirements
        materials = self.get_component_materials(component_id)
        result["materials"] = materials

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def get_components_by_pattern(self, pattern_id: int) -> List[Component]:
        """
        Get all components for a specific pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            List of components for the pattern
        """
        return self.repository.list(patternId=pattern_id)

    def get_components_by_type(
        self, component_type: Union[ComponentType, str]
    ) -> List[Component]:
        """
        Get components by type.

        Args:
            component_type: Type of component

        Returns:
            List of components of the specified type
        """
        # Convert string to enum if needed
        if isinstance(component_type, str):
            try:
                component_type = ComponentType[component_type.upper()]
                component_type = component_type.value
            except (KeyError, AttributeError):
                pass

        return self.repository.list(componentType=component_type)

    def clone_component(
        self, component_id: int, override_data: Optional[Dict[str, Any]] = None
    ) -> Component:
        """
        Clone an existing component to create a new one.

        Args:
            component_id: ID of the component to clone
            override_data: Optional data to override in the cloned component

        Returns:
            Newly created component entity

        Raises:
            EntityNotFoundException: If source component not found
        """
        with self.transaction():
            # Check if source component exists
            source = self.get_component_with_details(component_id)
            if not source:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Component", component_id)

            # Create new component data from source
            clone_data = {
                "name": f"Copy of {source['name']}",
                "componentType": source["componentType"],
                "patternId": source.get("patternId"),
                "description": source.get("description"),
                "attributes": source.get("attributes"),
                "pathData": source.get("pathData"),
                "position": source.get("position"),
                "rotation": source.get("rotation"),
                "isOptional": source.get("isOptional", False),
            }

            # Override with custom data if provided
            if override_data:
                clone_data.update(override_data)

            # Create new component
            new_component = self.create_component(clone_data)

            # Clone material requirements
            source_materials = source.get("materials", [])
            for material in source_materials:
                material_data = {
                    "component_id": new_component.id,
                    "material_id": material["material_id"],
                    "materialType": material["materialType"],
                    "quantity": material["quantity"],
                    "unit": material["unit"],
                    "isRequired": material.get("isRequired", True),
                }

                # Add alternative materials if available
                if (
                    "alternativeMaterialIds" in material
                    and material["alternativeMaterialIds"]
                ):
                    material_data["alternativeMaterialIds"] = material[
                        "alternativeMaterialIds"
                    ]

                self.add_material_requirement(new_component.id, material_data)

            return new_component

    @validate_input(validate_component_material)
    def add_material_requirement(
        self, component_id: int, data: Dict[str, Any]
    ) -> ComponentMaterial:
        """
        Add a material requirement to a component.

        Args:
            component_id: ID of the component
            data: Material requirement data with required fields
                Required fields:
                - material_id: ID of the material
                - materialType: Type of material
                - quantity: Required quantity
                - unit: Measurement unit
                Optional fields:
                - isRequired: Whether this material is required
                - alternativeMaterialIds: List of alternative material IDs
                - notes: Additional notes

        Returns:
            Created material requirement entity

        Raises:
            EntityNotFoundException: If component not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if component exists
            component = self.get_by_id(component_id)
            if not component:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Component", component_id)

            # Check if material exists if material service is available
            material_id = data.get("material_id")
            if material_id and self.material_service:
                material = self.material_service.get_by_id(material_id)
                if not material:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Material", material_id)

            # Set component ID
            data["component_id"] = component_id

            # Set default values if not provided
            if "isRequired" not in data:
                data["isRequired"] = True

            # Convert alternativeMaterialIds to JSON if it's a list
            if "alternativeMaterialIds" in data and isinstance(
                data["alternativeMaterialIds"], list
            ):
                data["alternativeMaterialIds"] = json.dumps(
                    data["alternativeMaterialIds"]
                )

            # Create material requirement
            requirement = self.material_repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    MaterialRequirementAdded(
                        component_id=component_id,
                        material_id=material_id,
                        material_type=data.get("materialType"),
                        quantity=data.get("quantity"),
                        unit=data.get("unit"),
                        user_id=user_id,
                    )
                )

            # Invalidate component cache
            if self.cache_service:
                self.cache_service.invalidate(f"Component:detail:{component_id}")

            return requirement

    def update_material_requirement(
        self, requirement_id: int, data: Dict[str, Any]
    ) -> ComponentMaterial:
        """
        Update a material requirement.

        Args:
            requirement_id: ID of the material requirement
            data: Updated requirement data

        Returns:
            Updated material requirement entity

        Raises:
            EntityNotFoundException: If requirement not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if requirement exists
            requirement = self.material_repository.get_by_id(requirement_id)
            if not requirement:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("ComponentMaterial", requirement_id)

            # Convert alternativeMaterialIds to JSON if it's a list
            if "alternativeMaterialIds" in data and isinstance(
                data["alternativeMaterialIds"], list
            ):
                data["alternativeMaterialIds"] = json.dumps(
                    data["alternativeMaterialIds"]
                )

            # Update requirement
            updated_requirement = self.material_repository.update(requirement_id, data)

            # Invalidate component cache
            if self.cache_service:
                self.cache_service.invalidate(
                    f"Component:detail:{updated_requirement.component_id}"
                )

            return updated_requirement

    def remove_material_requirement(self, requirement_id: int) -> bool:
        """
        Remove a material requirement from a component.

        Args:
            requirement_id: ID of the material requirement

        Returns:
            True if removal was successful

        Raises:
            EntityNotFoundException: If requirement not found
        """
        with self.transaction():
            # Check if requirement exists
            requirement = self.material_repository.get_by_id(requirement_id)
            if not requirement:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("ComponentMaterial", requirement_id)

            # Store component and material IDs for event
            component_id = requirement.component_id
            material_id = requirement.material_id

            # Remove requirement
            result = self.material_repository.delete(requirement_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    MaterialRequirementRemoved(
                        component_id=component_id,
                        material_id=material_id,
                        user_id=user_id,
                    )
                )

            # Invalidate component cache
            if self.cache_service:
                self.cache_service.invalidate(f"Component:detail:{component_id}")

            return result

    def get_component_materials(self, component_id: int) -> List[Dict[str, Any]]:
        """
        Get all material requirements for a component.

        Args:
            component_id: ID of the component

        Returns:
            List of material requirements with details
        """
        # Get requirements
        requirements = self.material_repository.list(component_id=component_id)

        result = []
        for req in requirements:
            req_dict = req.to_dict()

            # Parse alternativeMaterialIds if it's JSON
            if (
                "alternativeMaterialIds" in req_dict
                and req_dict["alternativeMaterialIds"]
            ):
                try:
                    req_dict["alternativeMaterialIds"] = json.loads(
                        req_dict["alternativeMaterialIds"]
                    )
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, convert to list if string with commas
                    if (
                        isinstance(req_dict["alternativeMaterialIds"], str)
                        and "," in req_dict["alternativeMaterialIds"]
                    ):
                        req_dict["alternativeMaterialIds"] = [
                            int(id.strip())
                            for id in req_dict["alternativeMaterialIds"].split(",")
                            if id.strip().isdigit()
                        ]
                    # Otherwise keep as is

            # Add material details if material service is available
            material_id = req_dict.get("material_id")
            if material_id and self.material_service:
                try:
                    material = self.material_service.get_by_id(material_id)
                    if material:
                        req_dict["material"] = {
                            "id": material.id,
                            "name": material.name,
                            "materialType": (
                                material.materialType
                                if hasattr(material, "materialType")
                                else None
                            ),
                            "status": (
                                material.status if hasattr(material, "status") else None
                            ),
                            "quantity": (
                                material.quantity
                                if hasattr(material, "quantity")
                                else None
                            ),
                            "unit": (
                                material.unit if hasattr(material, "unit") else None
                            ),
                        }
                except Exception as e:
                    logger.warning(f"Failed to get material for requirement: {str(e)}")

            result.append(req_dict)

        return result

    def calculate_material_requirements(
        self, pattern_id: int
    ) -> Dict[int, Dict[str, Any]]:
        """
        Calculate total material requirements for a pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            Dictionary of material requirements by material ID

        Raises:
            EntityNotFoundException: If pattern not found
        """
        # Check if pattern exists if pattern service is available
        if self.pattern_service:
            pattern = self.pattern_service.get_by_id(pattern_id)
            if not pattern:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Pattern", pattern_id)

        # Get all components for the pattern
        components = self.get_components_by_pattern(pattern_id)

        # Initialize requirements dictionary
        requirements = {}

        # Process each component
        for component in components:
            # Skip optional components in this calculation
            if component.isOptional:
                continue

            # Get material requirements for the component
            component_materials = self.get_component_materials(component.id)

            # Add to total requirements
            for material in component_materials:
                material_id = material.get("material_id")
                if not material_id:
                    continue

                # Initialize material entry if not exists
                if material_id not in requirements:
                    # Get material details if available
                    material_details = material.get("material", {})

                    requirements[material_id] = {
                        "id": material_id,
                        "name": material_details.get("name", f"Material {material_id}"),
                        "materialType": material_details.get(
                            "materialType", material.get("materialType")
                        ),
                        "unit": material_details.get("unit", material.get("unit")),
                        "quantity_required": 0,
                        "components": [],
                    }

                # Add quantity
                quantity = material.get("quantity", 0)
                requirements[material_id]["quantity_required"] += quantity

                # Add component reference
                requirements[material_id]["components"].append(
                    {
                        "component_id": component.id,
                        "component_name": component.name,
                        "quantity": quantity,
                    }
                )

        return requirements

    def _is_component_in_use(self, component_id: int) -> bool:
        """
        Check if a component is in use by projects.

        Args:
            component_id: ID of the component

        Returns:
            True if component is in use
        """
        # This would check project repositories to see if the component is used
        # For now, return False as a placeholder
        return False

    def _delete_component_materials(self, component_id: int) -> None:
        """
        Delete all material requirements for a component.

        Args:
            component_id: ID of the component
        """
        # Get all requirements
        requirements = self.material_repository.list(component_id=component_id)

        # Delete each requirement
        for req in requirements:
            self.material_repository.delete(req.id)
