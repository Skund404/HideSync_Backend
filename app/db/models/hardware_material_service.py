# File: app/services/hardware_material_service.py
"""
Hardware material service for the HideSync application.

This module provides specialized service methods for managing hardware materials,
including creation, updates, and hardware-specific business logic.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.material import HardwareMaterial
from app.db.models.enums import (
    MaterialType,
    HardwareType,
    HardwareMaterial as HardwareMaterialEnum,
    HardwareFinish
)
from app.services.material_service import MaterialService
from app.core.exceptions import (
    MaterialNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.schemas.hardware_material import (
    HardwareMaterialCreate,
    HardwareMaterialUpdate,
    HardwareMaterialResponse,
)


class HardwareMaterialService(MaterialService):
    """
    Service for managing hardware materials in the HideSync system.

    Provides specialized functionality for:
    - Hardware-specific validation and business rules
    - Hardware material categorization and attributes
    - Hardware-specific inventory operations
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            key_service=None,
    ):
        """
        Initialize HardwareMaterialService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            key_service: Optional key service for encryption/decryption
        """
        super().__init__(
            session,
            repository,
            security_context,
            event_bus,
            cache_service,
            key_service,
        )

    def create_hardware_material(
            self, material_data: Union[Dict[str, Any], HardwareMaterialCreate], user_id: Optional[int] = None
    ) -> HardwareMaterial:
        """
        Create a new hardware material with specialized validation.

        Args:
            material_data: Hardware material data
            user_id: ID of the user creating the material

        Returns:
            Created hardware material entity

        Raises:
            ValidationException: If material data validation fails
        """
        # Convert Pydantic model to dict if needed
        if not isinstance(material_data, dict):
            material_data = material_data.dict(exclude_unset=True)

        # Ensure material type is set correctly
        material_data["material_type"] = MaterialType.HARDWARE.value

        # Validate hardware-specific fields
        self._validate_hardware_material(material_data)

        # Create the material
        with self.transaction():
            material = self.repository.create_hardware(material_data)

            # Publish event if event bus exists
            if self.event_bus:
                event = self._create_created_event(material)
                if user_id:
                    event.user_id = user_id
                self.event_bus.publish(event)

            return material

    def update_hardware_material(
            self,
            material_id: int,
            material_data: Union[Dict[str, Any], HardwareMaterialUpdate],
            user_id: Optional[int] = None,
    ) -> HardwareMaterial:
        """
        Update a hardware material with specialized validation.

        Args:
            material_id: ID of the material to update
            material_data: Updated hardware material data
            user_id: ID of the user updating the material

        Returns:
            Updated hardware material entity

        Raises:
            MaterialNotFoundException: If material not found
            ValidationException: If material data validation fails
        """
        # Convert Pydantic model to dict if needed
        if not isinstance(material_data, dict):
            material_data = material_data.dict(exclude_unset=True, exclude_none=True)

        # Fetch the material to update
        with self.transaction():
            material = self.repository.get_by_id(material_id)

            if not material:
                raise MaterialNotFoundException(material_id)

            # Verify it's a hardware material
            if material.material_type != MaterialType.HARDWARE.value:
                raise BusinessRuleException(
                    f"Material with ID {material_id} is not a hardware material",
                    "INVALID_MATERIAL_TYPE",
                    {"expected_type": MaterialType.HARDWARE.value, "actual_type": material.material_type}
                )

            # Store original for event creation
            original = material.to_dict()

            # Validate hardware-specific fields
            self._validate_hardware_material(material_data, is_update=True)

            # Update the material
            updated = self.repository.update(material_id, material_data)

            # Publish event if event bus exists
            if self.event_bus:
                changes = {}
                for key, new_value in material_data.items():
                    old_value = original.get(key)
                    if old_value != new_value:
                        changes[key] = {"old": old_value, "new": new_value}

                event = self._create_updated_event(original, updated)
                if user_id:
                    event.user_id = user_id
                self.event_bus.publish(event)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Material:{material_id}")
                self.cache_service.invalidate(f"HardwareMaterial:{material_id}")

            return updated

    def get_hardware_materials(
            self,
            skip: int = 0,
            limit: int = 100,
            hardware_type: Optional[HardwareType] = None,
            hardware_material: Optional[HardwareMaterialEnum] = None,
            finish: Optional[HardwareFinish] = None,
            size: Optional[str] = None,
            color: Optional[str] = None,
    ) -> List[HardwareMaterial]:
        """
        Get hardware materials with specialized filtering options.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            hardware_type: Optional filter by hardware type
            hardware_material: Optional filter by hardware material
            finish: Optional filter by finish
            size: Optional filter by size
            color: Optional filter by color

        Returns:
            List of hardware materials matching the criteria
        """
        # Build filter criteria
        filters = {"material_type": MaterialType.HARDWARE.value}

        if hardware_type:
            filters["hardware_type"] = hardware_type

        if hardware_material:
            filters["hardware_material"] = hardware_material

        if finish:
            filters["finish"] = finish

        if size:
            filters["size"] = size

        if color:
            filters["color"] = color

        # Execute query
        return self.repository.find_by_criteria(filters, skip=skip, limit=limit)

    def get_hardware_material_by_id(self, material_id: int) -> HardwareMaterial:
        """
        Get a hardware material by ID with type validation.

        Args:
            material_id: ID of the hardware material

        Returns:
            Hardware material entity

        Raises:
            MaterialNotFoundException: If material not found
            BusinessRuleException: If material is not a hardware material
        """
        material = self.repository.get_by_id(material_id)

        if not material:
            raise MaterialNotFoundException(material_id)

        # Verify it's a hardware material
        if material.material_type != MaterialType.HARDWARE.value:
            raise BusinessRuleException(
                f"Material with ID {material_id} is not a hardware material",
                "INVALID_MATERIAL_TYPE",
                {"expected_type": MaterialType.HARDWARE.value, "actual_type": material.material_type}
            )

        return material

    def get_hardware_by_type_and_size(
            self,
            hardware_type: HardwareType,
            size: Optional[str] = None,
    ) -> List[HardwareMaterial]:
        """
        Find hardware materials by type and optional size.

        Args:
            hardware_type: Type of hardware
            size: Optional size specification

        Returns:
            List of matching hardware materials
        """
        filters = {
            "material_type": MaterialType.HARDWARE.value,
            "hardware_type": hardware_type,
        }

        if size:
            filters["size"] = size

        return self.repository.find_by_criteria(filters)

    def get_compatible_hardware(
            self,
            project_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get hardware materials compatible with a project.

        Args:
            project_id: ID of the project

        Returns:
            List of compatible hardware materials with compatibility scores

        Note:
            This is a placeholder implementation that would need to be
            integrated with project service logic to determine compatibility.
        """
        # This would require project service integration
        # For now, we'll return a basic implementation
        hardware_materials = self.get_hardware_materials()

        result = []
        for material in hardware_materials:
            # In a real implementation, this would check project requirements
            # against hardware attributes to calculate a compatibility score
            result.append({
                "material_id": material.id,
                "name": material.name,
                "hardware_type": material.hardware_type,
                "size": material.size,
                "compatibility_score": 100,  # Placeholder score
                "in_stock": material.quantity > 0,
                "quantity_available": material.quantity,
            })

        # Sort by compatibility score (descending)
        return sorted(result, key=lambda x: x["compatibility_score"], reverse=True)

    def _validate_hardware_material(self, data: Dict[str, Any], is_update: bool = False) -> None:
        """
        Validate hardware-specific fields and business rules.

        Args:
            data: Material data to validate
            is_update: Whether this is an update operation

        Raises:
            ValidationException: If validation fails
        """
        errors = {}

        # Check hardware type is valid
        if "hardware_type" in data and data["hardware_type"] is not None:
            try:
                HardwareType(data["hardware_type"])
            except ValueError:
                errors["hardware_type"] = [f"Invalid hardware type: {data['hardware_type']}"]

        # Check hardware material is valid
        if "hardware_material" in data and data["hardware_material"] is not None:
            try:
                HardwareMaterialEnum(data["hardware_material"])
            except ValueError:
                errors["hardware_material"] = [f"Invalid hardware material: {data['hardware_material']}"]

        # Check finish is valid
        if "finish" in data and data["finish"] is not None:
            try:
                HardwareFinish(data["finish"])
            except ValueError:
                errors["finish"] = [f"Invalid finish: {data['finish']}"]

        # If any errors were found, raise exception
        if errors:
            raise ValidationException("Hardware material validation failed", errors)