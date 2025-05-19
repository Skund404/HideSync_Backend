# File: app/db/models/dynamic_material.py (UPDATED - Add missing reverse relationships)
"""
Dynamic Material Management System for HideSync.

This module defines models for managing material types with dynamic properties,
allowing users to create custom material types with custom properties.

UPDATED: Added storage-related reverse relationships to complete the integration.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime, JSON,
    UniqueConstraint, Table
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
import json

from app.db.models.base import Base, TimestampMixin, ValidationMixin
from app.db.models.tag import material_tags


class MaterialType(Base, TimestampMixin):
    """
    Defines a type of material with customizable properties.
    """
    __tablename__ = "material_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    icon = Column(String(50))
    color_scheme = Column(String(50))
    _ui_config = Column("ui_config", Text)
    _storage_config = Column("storage_config", Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_system = Column(Boolean, default=False)
    visibility_level = Column(String(50), default="all")  # all, admin, or specific tier

    # Relationships
    properties = relationship(
        "MaterialTypeProperty",
        back_populates="material_type",
        cascade="all, delete-orphan"
    )
    translations = relationship(
        "MaterialTypeTranslation",
        back_populates="material_type",
        cascade="all, delete-orphan"
    )
    materials = relationship(
        "DynamicMaterial",
        back_populates="material_type",
        cascade="all, delete-orphan"
    )

    # JSON property handlers
    @property
    def ui_config(self):
        if self._ui_config:
            try:
                return json.loads(self._ui_config)
            except:
                return {}
        return {}

    @ui_config.setter
    def ui_config(self, value):
        if value is not None:
            self._ui_config = json.dumps(value)
        else:
            self._ui_config = None

    @property
    def storage_config(self):
        if self._storage_config:
            try:
                return json.loads(self._storage_config)
            except:
                return {}
        return {}

    @storage_config.setter
    def storage_config(self, value):
        if value is not None:
            self._storage_config = json.dumps(value)
        else:
            self._storage_config = None

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name


class MaterialTypeTranslation(Base):
    """
    Translations for material types.
    """
    __tablename__ = "material_type_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_type_id = Column(Integer, ForeignKey("material_types.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    material_type = relationship("MaterialType", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('material_type_id', 'locale', name='uq_material_type_translation'),
    )


class PropertyDefinition(Base, TimestampMixin):
    """
    Definition of a property that can be assigned to material types.
    """
    __tablename__ = "property_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    data_type = Column(String(50), nullable=False)  # string, number, boolean, enum, date, file, etc.
    group_name = Column(String(100))
    unit = Column(String(50))
    is_required = Column(Boolean, default=False)
    has_multiple_values = Column(Boolean, default=False)
    _validation_rules = Column("validation_rules", Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_system = Column(Boolean, default=False)
    enum_type_id = Column(Integer, ForeignKey("enum_types.id"))

    # Relationships
    translations = relationship(
        "PropertyDefinitionTranslation",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_options = relationship(
        "PropertyEnumOption",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_mappings = relationship(
        "PropertyEnumMapping",
        back_populates="property",
        cascade="all, delete-orphan"
    )
    enum_type = relationship("EnumType")
    material_type_properties = relationship(
        "MaterialTypeProperty",
        back_populates="property"
    )

    # JSON property handlers
    @property
    def validation_rules(self):
        if self._validation_rules:
            try:
                return json.loads(self._validation_rules)
            except:
                return {}
        return {}

    @validation_rules.setter
    def validation_rules(self, value):
        if value is not None:
            self._validation_rules = json.dumps(value)
        else:
            self._validation_rules = None

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name


class PropertyDefinitionTranslation(Base):
    """
    Translations for property definitions.
    """
    __tablename__ = "property_definition_translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)  # e.g., 'en', 'fr', 'es'
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    property = relationship("PropertyDefinition", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'locale', name='uq_property_definition_translation'),
    )


class PropertyEnumOption(Base):
    """
    Custom enum options for property definitions with enum data type.
    """
    __tablename__ = "property_enum_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), nullable=False)
    value = Column(String(100), nullable=False)
    display_value = Column(String(255), nullable=False)
    color = Column(String(50))
    display_order = Column(Integer, default=0)

    # Relationships
    property = relationship("PropertyDefinition", back_populates="enum_options")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'value', name='uq_property_enum_option'),
    )


class PropertyEnumMapping(Base):
    """
    Maps a property to an enum type from the dynamic enum system.
    """
    __tablename__ = "property_enum_mappings"

    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), primary_key=True)
    enum_type_id = Column(Integer, ForeignKey("enum_types.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    property = relationship("PropertyDefinition", back_populates="enum_mappings")
    enum_type = relationship("EnumType")


class MaterialTypeProperty(Base):
    """
    Junction table that associates properties with material types
    and defines their configuration within that material type.
    """
    __tablename__ = "material_type_properties"

    material_type_id = Column(Integer, ForeignKey("material_types.id", ondelete="CASCADE"), primary_key=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), primary_key=True)
    display_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_filterable = Column(Boolean, default=True)
    is_displayed_in_list = Column(Boolean, default=True)
    is_displayed_in_card = Column(Boolean, default=True)
    _default_value = Column("default_value", Text)

    # Relationships
    material_type = relationship("MaterialType", back_populates="properties")
    property = relationship("PropertyDefinition", back_populates="material_type_properties")

    # JSON property handlers
    @property
    def default_value(self):
        if self._default_value:
            try:
                return json.loads(self._default_value)
            except:
                return None
        return None

    @default_value.setter
    def default_value(self, value):
        if value is not None:
            self._default_value = json.dumps(value)
        else:
            self._default_value = None


class DynamicMaterial(Base, TimestampMixin):
    """
    Dynamic material model that can be customized based on material type.

    UPDATED: Added storage-related reverse relationships.
    """
    __tablename__ = "dynamic_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_type_id = Column(Integer, ForeignKey("material_types.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="in_stock")
    quantity = Column(Float, default=0)
    unit = Column(String(50), nullable=False)
    quality = Column(String(50))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    supplier = Column(String(255))  # Denormalized for convenience
    sku = Column(String(100))
    supplier_sku = Column(String(100))
    description = Column(Text)
    reorder_point = Column(Float, default=0)
    cost_price = Column(Float)
    sell_price = Column(Float)
    storage_location = Column(String(100))
    notes = Column(Text)
    thumbnail = Column(String(255))
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    material_type = relationship("MaterialType", back_populates="materials")
    property_values = relationship(
        "MaterialPropertyValue",
        back_populates="material",
        cascade="all, delete-orphan"
    )
    media = relationship(
        "MediaAsset",
        secondary="material_media",
        backref="materials"
    )
    tags = relationship(
        "Tag",
        secondary=material_tags,
        back_populates="materials"
    )

    # ADDED: Storage-related reverse relationships
    storage_cells = relationship(
        "StorageCell",
        back_populates="material",
        cascade="all, delete-orphan"
    )
    storage_assignments = relationship(
        "StorageAssignment",
        back_populates="material",
        cascade="all, delete-orphan"
    )
    storage_moves = relationship(
        "StorageMove",
        back_populates="material",
        cascade="all, delete-orphan"
    )

    # ADDED: Storage-related hybrid properties
    @hybrid_property
    def current_storage_locations(self):
        """Get all current storage locations for this material."""
        return [assignment.location for assignment in self.storage_assignments if assignment.location]

    @hybrid_property
    def total_assigned_quantity(self):
        """Get total quantity assigned to storage locations."""
        return sum(assignment.quantity or 0 for assignment in self.storage_assignments)

    @hybrid_property
    def storage_locations_count(self):
        """Get count of storage locations this material is stored in."""
        return len(set(assignment.storage_id for assignment in self.storage_assignments))

    @hybrid_property
    def is_multi_location_stored(self):
        """Check if material is stored in multiple locations."""
        return self.storage_locations_count > 1

    @hybrid_property
    def primary_storage_location(self):
        """Get the primary (first/largest quantity) storage location."""
        if not self.storage_assignments:
            return None
        # Return location with largest quantity
        primary_assignment = max(self.storage_assignments, key=lambda a: a.quantity or 0)
        return primary_assignment.location

    def get_recent_moves(self, limit: int = 5):
        """Get recent storage moves for this material."""
        return sorted(
            self.storage_moves,
            key=lambda m: m.move_date or "",
            reverse=True
        )[:limit]

    # Existing calculated properties
    @hybrid_property
    def value(self):
        """Calculate the total value of inventory"""
        if self.cost_price is None:
            return None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * self.cost_price

    @hybrid_property
    def total_selling_value(self):
        """Calculate the total selling value of inventory"""
        if self.sell_price is None:
            return None
        quantity = self.quantity if self.quantity is not None else 0.0
        return quantity * self.sell_price


class MaterialPropertyValue(Base):
    """
    Stores property values for materials based on their property definitions.
    Uses a polymorphic storage approach to store different data types.
    """
    __tablename__ = "material_property_values"

    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="CASCADE"), primary_key=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id"), primary_key=True)

    # Polymorphic storage for different data types
    value_string = Column(Text)
    value_number = Column(Float)
    value_boolean = Column(Boolean)
    value_date = Column(String(50))  # Store as ISO string for SQLite compatibility
    value_enum_id = Column(Integer)  # References an enum value in the respective enum table
    value_file_id = Column(String(100))  # Reference to file/media asset
    value_reference_id = Column(Integer)  # Reference to another entity

    # Relationships
    material = relationship("DynamicMaterial", back_populates="property_values")
    property = relationship("PropertyDefinition")


class MaterialMedia(Base):
    """
    Associates media assets with materials, tracking primary images and order.
    """
    __tablename__ = "material_media"

    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="CASCADE"), primary_key=True)
    media_asset_id = Column(String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True)
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Create a unique constraint to ensure only one primary image per material
    __table_args__ = (
        UniqueConstraint('material_id', 'is_primary',
                         name='uq_material_primary_media',
                         sqlite_where=is_primary),
    )