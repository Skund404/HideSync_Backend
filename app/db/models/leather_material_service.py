# File: app/services/leather_material_service.py
"""
Leather material service for the HideSync application.

This module provides specialized service methods for managing leather materials,
including creation, updates, and leather-specific business logic.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models.material import LeatherMaterial
from app.db.models.enums import MaterialType, LeatherType, LeatherFinish
from app.services.material_service import MaterialService
from app.core.exceptions import (
    MaterialNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.schemas.leather_material import (
    LeatherMaterialCreate,
    LeatherMaterialUpdate,
    LeatherMaterialResponse,
)


class LeatherMaterialService(MaterialService):
    """
    Service for managing leather materials in the HideSync system.

    Provides specialized functionality for:
    - Leather-specific validation and business rules
    - Leather material categorization and attributes
    - Leather-specific inventory operations
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
        Initialize LeatherMaterialService with dependencies.

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

    def create_leather_material(
        self,
        material_data: Union[Dict[str, Any], LeatherMaterialCreate],
        user_id: Optional[int] = None,
    ) -> LeatherMaterial:
        """
        Create a new leather material with specialized validation.

        Args:
            material_data: Leather material data
            user_id: ID of the user creating the material

        Returns:
            Created leather material entity

        Raises:
            ValidationException: If material data validation fails
        """
        # Convert Pydantic model to dict if needed
        if not isinstance(material_data, dict):
            material_data = material_data.dict(exclude_unset=True)

        # Ensure material type is set correctly
        material_data["material_type"] = MaterialType.LEATHER.value

        # Validate leather-specific fields
        self._validate_leather_material(material_data)

        # Create the material
        with self.transaction():
            material = self.repository.create_leather(material_data)

            # Publish event if event bus exists
            if self.event_bus:
                event = self._create_created_event(material)
                if user_id:
                    event.user_id = user_id
                self.event_bus.publish(event)

            return material

    def update_leather_material(
        self,
        material_id: int,
        material_data: Union[Dict[str, Any], LeatherMaterialUpdate],
        user_id: Optional[int] = None,
    ) -> LeatherMaterial:
        """
        Update a leather material with specialized validation.

        Args:
            material_id: ID of the material to update
            material_data: Updated leather material data
            user_id: ID of the user updating the material

        Returns:
            Updated leather material entity

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

            # Verify it's a leather material
            if material.material_type != MaterialType.LEATHER.value:
                raise BusinessRuleException(
                    f"Material with ID {material_id} is not a leather material",
                    "INVALID_MATERIAL_TYPE",
                    {
                        "expected_type": MaterialType.LEATHER.value,
                        "actual_type": material.material_type,
                    },
                )

            # Store original for event creation
            original = material.to_dict()

            # Validate leather-specific fields
            self._validate_leather_material(material_data, is_update=True)

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
                self.cache_service.invalidate(f"LeatherMaterial:{material_id}")

            return updated

    def get_leather_materials(
        self,
        skip: int = 0,
        limit: int = 100,
        leather_type: Optional[LeatherType] = None,
        min_thickness: Optional[float] = None,
        max_thickness: Optional[float] = None,
        animal_source: Optional[str] = None,
        finish: Optional[LeatherFinish] = None,
        color: Optional[str] = None,
        is_full_hide: Optional[bool] = None,
    ) -> List[LeatherMaterial]:
        """
        Get leather materials with specialized filtering options.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            leather_type: Optional filter by leather type
            min_thickness: Optional minimum thickness
            max_thickness: Optional maximum thickness
            animal_source: Optional filter by animal source
            finish: Optional filter by finish
            color: Optional filter by color
            is_full_hide: Optional filter for full hides

        Returns:
            List of leather materials matching the criteria
        """
        # Build filter criteria
        filters = {"material_type": MaterialType.LEATHER.value}

        if leather_type:
            filters["leather_type"] = leather_type

        if animal_source:
            filters["animal_source"] = animal_source

        if finish:
            filters["finish"] = finish

        if color:
            filters["color"] = color

        if is_full_hide is not None:
            filters["is_full_hide"] = is_full_hide

        # Execute query with thickness filters handled separately
        materials = self.repository.find_by_criteria(filters, skip=skip, limit=limit)

        # Apply thickness filters in memory if needed
        if min_thickness is not None or max_thickness is not None:
            filtered_materials = []
            for material in materials:
                if material.thickness is None:
                    continue

                if min_thickness is not None and material.thickness < min_thickness:
                    continue

                if max_thickness is not None and material.thickness > max_thickness:
                    continue

                filtered_materials.append(material)

            return filtered_materials

        return materials

    def get_leather_material_by_id(self, material_id: int) -> LeatherMaterial:
        """
        Get a leather material by ID with type validation.

        Args:
            material_id: ID of the leather material

        Returns:
            Leather material entity

        Raises:
            MaterialNotFoundException: If material not found
            BusinessRuleException: If material is not a leather material
        """
        material = self.repository.get_by_id(material_id)

        if not material:
            raise MaterialNotFoundException(material_id)

        # Verify it's a leather material
        if material.material_type != MaterialType.LEATHER.value:
            raise BusinessRuleException(
                f"Material with ID {material_id} is not a leather material",
                "INVALID_MATERIAL_TYPE",
                {
                    "expected_type": MaterialType.LEATHER.value,
                    "actual_type": material.material_type,
                },
            )

        return material

    def get_leather_material_by_attributes(
        self,
        thickness: Optional[float] = None,
        color: Optional[str] = None,
        leather_type: Optional[LeatherType] = None,
        animal_source: Optional[str] = None,
    ) -> List[LeatherMaterial]:
        """
        Find leather materials by specific attributes.

        Args:
            thickness: Optional thickness in mm
            color: Optional color name
            leather_type: Optional leather type
            animal_source: Optional animal source

        Returns:
            List of matching leather materials
        """
        filters = {"material_type": MaterialType.LEATHER.value}

        if thickness:
            filters["thickness"] = thickness

        if color:
            filters["color"] = color

        if leather_type:
            filters["leather_type"] = leather_type

        if animal_source:
            filters["animal_source"] = animal_source

        return self.repository.find_by_criteria(filters)

    def calculate_leather_area_value(self, material_id: int) -> Dict[str, Any]:
        """
        Calculate the value per square foot/meter of a leather material.

        Args:
            material_id: ID of the leather material

        Returns:
            Dictionary with value metrics

        Raises:
            MaterialNotFoundException: If material not found
            BusinessRuleException: If material is not a leather material
        """
        material = self.get_leather_material_by_id(material_id)

        # Calculate area-based metrics
        if not material.area or material.area <= 0:
            raise BusinessRuleException(
                f"Cannot calculate area value - material {material_id} has no valid area",
                "MISSING_AREA",
                {"material_id": material_id},
            )

        if not material.cost_price:
            raise BusinessRuleException(
                f"Cannot calculate area value - material {material_id} has no cost price",
                "MISSING_COST",
                {"material_id": material_id},
            )

        value_per_unit_area = material.cost_price / material.area
        total_area = material.area * material.quantity
        total_value = material.cost_price * material.quantity

        return {
            "material_id": material_id,
            "material_name": material.name,
            "area_per_unit": material.area,
            "total_area": total_area,
            "value_per_unit_area": value_per_unit_area,
            "total_value": total_value,
            "unit": material.unit.value if material.unit else None,
        }

    def _validate_leather_material(
        self, data: Dict[str, Any], is_update: bool = False
    ) -> None:
        """
        Validate leather-specific fields and business rules.

        Args:
            data: Material data to validate
            is_update: Whether this is an update operation

        Raises:
            ValidationException: If validation fails
        """
        errors = {}

        # Check leather type is valid
        if "leather_type" in data and data["leather_type"] is not None:
            try:
                LeatherType(data["leather_type"])
            except ValueError:
                errors["leather_type"] = [
                    f"Invalid leather type: {data['leather_type']}"
                ]

        # Check finish is valid
        if "finish" in data and data["finish"] is not None:
            try:
                LeatherFinish(data["finish"])
            except ValueError:
                errors["finish"] = [f"Invalid finish: {data['finish']}"]

        # Validate thickness is positive
        if "thickness" in data and data["thickness"] is not None:
            if data["thickness"] <= 0:
                errors["thickness"] = ["Thickness must be positive"]

        # Validate area is positive
        if "area" in data and data["area"] is not None:
            if data["area"] <= 0:
                errors["area"] = ["Area must be positive"]

        # If any errors were found, raise exception
        if errors:
            raise ValidationException("Leather material validation failed", errors)
