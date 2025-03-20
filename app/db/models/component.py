# File: app/db/models/component.py
"""
Component and ComponentMaterial models for the Leathercraft ERP system.

This module defines the Component model representing individual parts used
in leatherworking projects, and the ComponentMaterial model that tracks
materials required for each component.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ComponentType, MaterialType, MeasurementUnit


class Component(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Component model representing individual parts used in projects.

    This model defines the individual pieces or components that make up
    a leatherworking project, including their design, dimensions, and
    relationship to patterns and materials.

    Attributes:
        pattern_id: ID of the associated pattern
        name: Component name/description
        description: Detailed component description
        component_type: Type of component
        attributes: Additional attributes as JSON
        path_data: SVG path data for component shape
        position: Position information as JSON
        rotation: Rotation in degrees
        is_optional: Whether this component is optional
        author_name: Creator of the component
    """

    __tablename__ = "components"
    __validated_fields__: ClassVar[Set[str]] = {"name", "component_type"}

    # Relationships
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    component_type = Column(Enum(ComponentType))

    # Design information
    attributes = Column(JSON, nullable=True)
    path_data = Column(Text)  # SVG path data
    position = Column(JSON, nullable=True)
    rotation = Column(Integer, default=0)

    # Flags
    is_optional = Column(Boolean, default=False)

    # Metadata
    author_name = Column(String(100))

    # Relationships
    pattern = relationship("Pattern", back_populates="components")
    project_components = relationship("ProjectComponent", back_populates="component")
    materials = relationship(
        "ComponentMaterial", back_populates="component", cascade="all, delete-orphan"
    )
    picking_list_items = relationship("PickingListItem", back_populates="component")

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate component name.

        Args:
            key: Field name ('name')
            name: Component name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Component name must be at least 2 characters")
        return name.strip()

    @validates("component_type")
    def validate_component_type(
        self, key: str, component_type: ComponentType
    ) -> ComponentType:
        """
        Validate component type.

        Args:
            key: Field name ('component_type')
            component_type: Component type to validate

        Returns:
            Validated component type
        """
        if not component_type:
            raise ValueError("Component type is required")
        return component_type

    def get_total_material_requirements(self) -> Dict[str, float]:
        """
        Calculate total material requirements for this component.

        Returns:
            Dictionary mapping material IDs to required quantities
        """
        requirements = {}
        for material_req in self.materials:
            material_id = material_req.material_id
            quantity = material_req.quantity

            if material_id in requirements:
                requirements[material_id] += quantity
            else:
                requirements[material_id] = quantity

        return requirements

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Component instance to a dictionary.

        Returns:
            Dictionary representation of the component
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.component_type:
            result["component_type"] = self.component_type.name

        # Handle JSON fields
        for field in ["attributes", "position"]:
            if isinstance(result.get(field), str):
                import json

                try:
                    result[field] = json.loads(result[field])
                except:
                    result[field] = {}

        return result

    def __repr__(self) -> str:
        """Return string representation of the Component."""
        return (
            f"<Component(id={self.id}, name='{self.name}', type={self.component_type})>"
        )


class ComponentMaterial(AbstractBase, ValidationMixin):
    """
    ComponentMaterial model linking components to required materials.

    This model tracks the materials required for each component, including
    quantities, types, and alternative options.

    Attributes:
        component_id: ID of the associated component
        material_id: ID of the required material
        material_type: Type of material
        quantity: Required quantity
        unit: Unit of measurement
        is_required: Whether this material is required
        alternative_material_ids: Alternative material options
        notes: Additional notes
    """

    __tablename__ = "component_materials"
    __validated_fields__: ClassVar[Set[str]] = {
        "quantity",
        "material_id",
        "component_id",
    }

    # Relationships
    component_id = Column(Integer, ForeignKey("components.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)

    # Material requirements
    material_type = Column(Enum(MaterialType))
    quantity = Column(Float, nullable=False)
    unit = Column(Enum(MeasurementUnit), nullable=False)

    # Options
    is_required = Column(Boolean, default=True)
    alternative_material_ids = Column(JSON, nullable=True)  # Array of material IDs
    notes = Column(Text)

    # Relationships
    component = relationship("Component", back_populates="materials")
    material = relationship("Material", back_populates="component_materials")

    @validates("quantity")
    def validate_quantity(self, key: str, quantity: float) -> float:
        """
        Validate material quantity.

        Args:
            key: Field name ('quantity')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is less than or equal to 0
        """
        if quantity <= 0:
            raise ValueError("Material quantity must be greater than 0")
        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ComponentMaterial instance to a dictionary.

        Returns:
            Dictionary representation of the component material
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.material_type:
            result["material_type"] = self.material_type.name
        if self.unit:
            result["unit"] = self.unit.name

        # Handle JSON fields
        if isinstance(result.get("alternative_material_ids"), str):
            import json

            try:
                result["alternative_material_ids"] = json.loads(
                    result["alternative_material_ids"]
                )
            except:
                result["alternative_material_ids"] = []

        return result

    def __repr__(self) -> str:
        """Return string representation of the ComponentMaterial."""
        return f"<ComponentMaterial(component_id={self.component_id}, material_id={self.material_id}, quantity={self.quantity})>"
