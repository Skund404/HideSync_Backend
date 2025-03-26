# File: app/db/models/component.py
"""
Component and ComponentMaterial models for the Leathercraft ERP system.

This module defines the Component model representing individual parts used
in leatherworking projects, and the ComponentMaterial model that tracks
materials required for each component.
"""

from __future__ import annotations # Allows type hinting models defined later

from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Set

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime, # Added if needed by base classes
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, validates

# Assuming base classes and enums are imported
from app.db.models.base import AbstractBase, TimestampMixin, ValidationMixin
from app.db.models.enums import ComponentType, MaterialType, MeasurementUnit


# Forward declarations if needed
# class Pattern: pass
# class ProjectComponent: pass
# class ComponentMaterial: pass
# class PickingListItem: pass
# class ProjectTemplateComponent: pass # <<< Important


class Component(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Component model representing individual parts used in projects.
    ... (rest of docstring) ...
    """

    __tablename__ = "components"
    __validated_fields__: ClassVar[Set[str]] = {"name", "component_type"}

    # --- Primary Key ---
    id = Column(Integer, primary_key=True) # Assuming PK is needed

    # --- Foreign Keys ---
    # Ensure Integer matches Pattern.id type
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)

    # --- Basic information ---
    name = Column(String(255), nullable=False)
    description = Column(Text)
    component_type = Column(Enum(ComponentType))

    # --- Design information ---
    attributes = Column(JSON, nullable=True)
    path_data = Column(Text)  # SVG path data
    position = Column(JSON, nullable=True)
    rotation = Column(Integer, default=0)

    # --- Flags ---
    is_optional = Column(Boolean, default=False)

    # --- Metadata ---
    author_name = Column(String(100))

    # --- RELATIONSHIPS ---

    # Many-to-One relationship FROM Component TO Pattern
    pattern = relationship("Pattern", back_populates="components") # Assumes Pattern.components exists

    # One-to-Many relationship FROM Component TO ProjectComponent (Association Object)
    # Shows which specific projects use this component
    project_components = relationship("ProjectComponent", back_populates="component") # Assumes ProjectComponent.component exists

    # One-to-Many relationship FROM Component TO ComponentMaterial (Association Object)
    # Shows which materials are needed for this component
    materials = relationship(
        "ComponentMaterial", back_populates="component", cascade="all, delete-orphan"
    )

    # One-to-Many relationship FROM Component TO PickingListItem
    # Shows which picking lists include this component directly (if applicable)
    picking_list_items = relationship("PickingListItem", back_populates="component") # Assumes PickingListItem.component exists

    # --- ADD THIS RELATIONSHIP ---
    # One-to-Many relationship FROM Component TO ProjectTemplateComponent (Association Object)
    # Shows which project templates include this component
    template_components = relationship(
        "ProjectTemplateComponent",
        # This back_populates value MUST match the name of the relationship
        # attribute on ProjectTemplateComponent that points back to Component.
        back_populates="component",
        cascade="all, delete-orphan", # If deleting component removes it from templates
        passive_deletes=True,
    )
    # --- END ADDED RELATIONSHIP ---

    # --- End Relationships ---


    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Validate component name."""
        if not name or len(name.strip()) < 2:
            raise ValueError("Component name must be at least 2 characters")
        return name.strip()

    @validates("component_type")
    def validate_component_type(
        self, key: str, component_type: ComponentType
    ) -> ComponentType:
        """Validate component type."""
        if not component_type:
            raise ValueError("Component type is required")
        return component_type

    def get_total_material_requirements(self) -> Dict[int, float]: # Changed key type hint
        """Calculate total material requirements for this component."""
        requirements: Dict[int, float] = {}
        for material_req in self.materials:
            material_id = material_req.material_id
            quantity = material_req.quantity

            if material_id is not None: # Check if material_id is valid
                requirements[material_id] = requirements.get(material_id, 0) + quantity

        return requirements

    def to_dict(self) -> Dict[str, Any]:
        """Convert Component instance to a dictionary."""
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
                except json.JSONDecodeError: # Catch specific error
                    result[field] = {} # Default to empty dict on error

        # Add calculated requirements if desired
        # result["material_requirements"] = self.get_total_material_requirements()

        return result

    def __repr__(self) -> str:
        """Return string representation of the Component."""
        # Use getattr for safety before ID is assigned
        return f"<Component(id={getattr(self, 'id', None)}, name='{self.name}', type={self.component_type})>"


# --- ComponentMaterial class remains the same ---
class ComponentMaterial(AbstractBase, ValidationMixin):
    """
    ComponentMaterial model linking components to required materials.
    ... (rest of docstring and class definition) ...
    """
    __tablename__ = "component_materials"
    __validated_fields__: ClassVar[Set[str]] = {
        "quantity",
        "material_id",
        "component_id",
    }

    # Relationships
    # Ensure Integer matches Component.id and Material.id types
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
        """Validate material quantity."""
        if quantity <= 0:
            raise ValueError("Material quantity must be greater than 0")
        return quantity

    def to_dict(self) -> Dict[str, Any]:
        """Convert ComponentMaterial instance to a dictionary."""
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
            except json.JSONDecodeError:
                result["alternative_material_ids"] = []

        return result

    def __repr__(self) -> str:
        """Return string representation of the ComponentMaterial."""
        return f"<ComponentMaterial(component_id={self.component_id}, material_id={self.material_id}, quantity={self.quantity})>"

