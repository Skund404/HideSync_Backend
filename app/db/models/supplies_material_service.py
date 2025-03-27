# File: app/services/supplies_material_service.py
"""
Supplies material service for the HideSync application.

This module provides specialized service methods for managing supplies materials,
including creation, updates, and supplies-specific business logic.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.material import SuppliesMaterial
from app.db.models.enums import MaterialType
from app.services.material_service import MaterialService
from app.core.exceptions import (
    MaterialNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.schemas.supplies_material import (
    SuppliesMaterialCreate,
    SuppliesMaterialUpdate,
    SuppliesMaterialResponse,
)


class SuppliesMaterialService(MaterialService):
    """
    Service for managing supplies materials in the HideSync system.

    Provides specialized functionality for:
    - Supplies-specific validation and business rules
    - Supplies material categorization and attributes
    - Supplies-specific inventory operations
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
        Initialize SuppliesMaterialService with dependencies.

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

    def create_supplies_material(
        self,
        material_data: Union[Dict[str, Any], SuppliesMaterialCreate],
        user_id: Optional[int] = None,
    ) -> SuppliesMaterial:
        """
        Create a new supplies material with specialized validation.

        Args:
            material_data: Supplies material data
            user_id: ID of the user creating the material

        Returns:
            Created supplies material entity

        Raises:
            ValidationException: If material data validation fails
        """
        # Convert Pydantic model to dict if needed
        if not isinstance(material_data, dict):
            material_data = material_data.dict(exclude_unset=True)

        # Ensure material type is set correctly
        material_data["material_type"] = MaterialType.SUPPLIES.value

        # Validate supplies-specific fields
        self._validate_supplies_material(material_data)

        # Create the material
        with self.transaction():
            material = self.repository.create_supplies(material_data)

            # Publish event if event bus exists
            if self.event_bus:
                event = self._create_created_event(material)
                if user_id:
                    event.user_id = user_id
                self.event_bus.publish(event)

            return material

    def update_supplies_material(
        self,
        material_id: int,
        material_data: Union[Dict[str, Any], SuppliesMaterialUpdate],
        user_id: Optional[int] = None,
    ) -> SuppliesMaterial:
        """
        Update a supplies material with specialized validation.

        Args:
            material_id: ID of the material to update
            material_data: Updated supplies material data
            user_id: ID of the user updating the material

        Returns:
            Updated supplies material entity

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

            # Verify it's a supplies material
            if material.material_type != MaterialType.SUPPLIES.value:
                raise BusinessRuleException(
                    f"Material with ID {material_id} is not a supplies material",
                    "INVALID_MATERIAL_TYPE",
                    {
                        "expected_type": MaterialType.SUPPLIES.value,
                        "actual_type": material.material_type,
                    },
                )

            # Store original for event creation
            original = material.to_dict()

            # Validate supplies-specific fields
            self._validate_supplies_material(material_data, is_update=True)

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
                self.cache_service.invalidate(f"SuppliesMaterial:{material_id}")

            return updated

    def get_supplies_materials(
        self,
        skip: int = 0,
        limit: int = 100,
        supplies_type: Optional[str] = None,
        color: Optional[str] = None,
        thread_thickness: Optional[str] = None,
        material_composition: Optional[str] = None,
        min_volume: Optional[float] = None,
        max_volume: Optional[float] = None,
        min_length: Optional[float] = None,
        max_length: Optional[float] = None,
    ) -> List[SuppliesMaterial]:
        """
        Get supplies materials with specialized filtering options.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            supplies_type: Optional filter by supplies type
            color: Optional filter by color
            thread_thickness: Optional filter by thread thickness
            material_composition: Optional filter by material composition
            min_volume: Optional minimum volume
            max_volume: Optional maximum volume
            min_length: Optional minimum length
            max_length: Optional maximum length

        Returns:
            List of supplies materials matching the criteria
        """
        # Build filter criteria
        filters = {"material_type": MaterialType.SUPPLIES.value}

        if supplies_type:
            filters["supplies_material_type"] = supplies_type

        if color:
            filters["color"] = color

        if thread_thickness:
            filters["thread_thickness"] = thread_thickness

        if material_composition:
            filters["material_composition"] = material_composition

        # Execute query
        materials = self.repository.find_by_criteria(filters, skip=skip, limit=limit)

        # Apply range filters in memory if needed
        filtered_materials = []
        for material in materials:
            # Volume filters
            if min_volume is not None and (
                material.volume is None or material.volume < min_volume
            ):
                continue

            if max_volume is not None and (
                material.volume is not None and material.volume > max_volume
            ):
                continue

            # Length filters
            if min_length is not None and (
                material.length is None or material.length < min_length
            ):
                continue

            if max_length is not None and (
                material.length is not None and material.length > max_length
            ):
                continue

            filtered_materials.append(material)

        return filtered_materials

    def get_supplies_material_by_id(self, material_id: int) -> SuppliesMaterial:
        """
        Get a supplies material by ID with type validation.

        Args:
            material_id: ID of the supplies material

        Returns:
            Supplies material entity

        Raises:
            MaterialNotFoundException: If material not found
            BusinessRuleException: If material is not a supplies material
        """
        material = self.repository.get_by_id(material_id)

        if not material:
            raise MaterialNotFoundException(material_id)

        # Verify it's a supplies material
        if material.material_type != MaterialType.SUPPLIES.value:
            raise BusinessRuleException(
                f"Material with ID {material_id} is not a supplies material",
                "INVALID_MATERIAL_TYPE",
                {
                    "expected_type": MaterialType.SUPPLIES.value,
                    "actual_type": material.material_type,
                },
            )

        return material

    def get_supplies_by_type(self, supplies_type: str) -> List[SuppliesMaterial]:
        """
        Find supplies materials by specific type.

        Args:
            supplies_type: Type of supplies

        Returns:
            List of matching supplies materials
        """
        filters = {
            "material_type": MaterialType.SUPPLIES.value,
            "supplies_material_type": supplies_type,
        }

        return self.repository.find_by_criteria(filters)

    def get_consumable_usage_rate(
        self, material_id: int, time_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate the usage rate of a consumable supplies material.

        Args:
            material_id: ID of the supplies material
            time_period_days: Time period in days for usage calculation

        Returns:
            Dictionary with usage metrics

        Raises:
            MaterialNotFoundException: If material not found
            BusinessRuleException: If material is not a supplies material
        """
        material = self.get_supplies_material_by_id(material_id)

        # Calculate usage rate
        # In a real implementation, this would analyze transaction history
        # For now, we'll return a placeholder implementation

        # Get usage transactions for the time period
        current_date = datetime.now()

        # This would use transaction repository in a real implementation
        # For now, we'll use placeholder data
        usage_metrics = {
            "material_id": material_id,
            "material_name": material.name,
            "supplies_type": material.supplies_material_type,
            "current_quantity": material.quantity,
            "total_used_30d": 5.0,  # Placeholder
            "usage_rate_per_day": 0.167,  # Placeholder
            "estimated_days_remaining": (
                30 if material.quantity > 0 else 0
            ),  # Placeholder
            "reorder_recommendation": material.quantity < material.reorder_point,
        }

        return usage_metrics

    def _validate_supplies_material(
        self, data: Dict[str, Any], is_update: bool = False
    ) -> None:
        """
        Validate supplies-specific fields and business rules.

        Args:
            data: Material data to validate
            is_update: Whether this is an update operation

        Raises:
            ValidationException: If validation fails
        """
        errors = {}

        # Validate volume is positive if provided
        if "volume" in data and data["volume"] is not None:
            if data["volume"] <= 0:
                errors["volume"] = ["Volume must be positive"]

        # Validate length is positive if provided
        if "length" in data and data["length"] is not None:
            if data["length"] <= 0:
                errors["length"] = ["Length must be positive"]

        # Validate supplies type is provided (for create)
        if not is_update and "supplies_material_type" not in data:
            errors["supplies_material_type"] = ["Supplies material type is required"]

        # If any errors were found, raise exception
        if errors:
            raise ValidationException("Supplies material validation failed", errors)
