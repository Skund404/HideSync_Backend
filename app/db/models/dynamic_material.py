# app/db/models/dynamic_material.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from app.db.models.base import Base, TimestampMixin


class MaterialType(Base, TimestampMixin):
    """
    Defines a type of material with its associated properties.

    This model allows users to create custom material types (beyond the
    system-provided ones like leather, hardware, supplies) with dynamic
    properties specific to their needs.
    """
    __tablename__ = "material_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    icon = Column(String(255))
    color_scheme = Column(String(50))
    _ui_config = Column("ui_config", Text)
    _storage_config = Column("storage_config", Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_system = Column(Boolean, default=False)
    visibility_level = Column(String(50), default="all")

    # Relationships
    properties = relationship(
        "PropertyDefinition",
        secondary="material_type_properties",
        backref="material_types"
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

    # JSON property handling for SQLite
    @property
    def ui_config(self):
        if self._ui_config:
            return json.loads(self._ui_config)
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
            return json.loads(self._storage_config)
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
    Localized translations for material types.
    """
    __tablename__ = "material_type_translations"

    id = Column(Integer, primary_key=True, index=True)
    material_type_id = Column(Integer, ForeignKey("material_types.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)

    material_type = relationship("MaterialType", back_populates="translations")

    __table_args__ = (
        UniqueConstraint('material_type_id', 'locale', name='uq_material_type_translation'),
    )


class PropertyDefinition(Base, TimestampMixin):
    """
    Defines a property that can be used across different material types.

    Properties can be of different data types (string, number, boolean, enum, etc.)
    and can be reused across multiple material types.
    """
    __tablename__ = "property_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    data_type = Column(String(50), nullable=False)  # string, number, boolean, enum, date, reference, file
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

    # JSON property handling for SQLite
    @property
    def validation_rules(self):
        if self._validation_rules:
            return json.loads(self._validation_rules)
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

    def get_enum_values(self, db):
        """Get enum values from the dynamic enum system or custom options"""
        if self.enum_type_id:
            # Use the dynamic enum system
            from app.services.enum_service import EnumService
            enum_service = EnumService(db)
            return enum_service.get_enum_values(self.enum_type.system_name)
        else:
            # Use custom property enum options
            return [
                {"id": opt.id, "value": opt.value, "display_value": opt.display_value}
                for opt in self.enum_options
            ]


class PropertyDefinitionTranslation(Base):
    """
    Localized translations for property definitions.
    """
    __tablename__ = "property_definition_translations"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)

    property = relationship("PropertyDefinition", back_populates="translations")

    __table_args__ = (
        UniqueConstraint('property_id', 'locale', name='uq_property_definition_translation'),
    )


class PropertyEnumOption(Base):
    """
    Custom enum options for properties that don't use the dynamic enum system.
    """
    __tablename__ = "property_enum_options"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), nullable=False)
    value = Column(String(100), nullable=False)
    display_value = Column(String(255), nullable=False)
    color = Column(String(50))
    display_order = Column(Integer, default=0)

    property = relationship("PropertyDefinition", back_populates="enum_options")

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

    property = relationship("PropertyDefinition", back_populates="enum_mappings")
    enum_type = relationship("EnumType")


class MaterialTypeProperty(Base):
    """
    Junction table linking material types to property definitions,
    with additional metadata about the relationship.
    """
    __tablename__ = "material_type_properties"

    material_type_id = Column(Integer, ForeignKey("material_types.id", ondelete="CASCADE"), primary_key=True)
    property_id = Column(Integer, ForeignKey("property_definitions.id", ondelete="CASCADE"), primary_key=True)
    display_order = Column(Integer, default=0)
    is_required = Column(Boolean)
    is_filterable = Column(Boolean, default=True)
    is_displayed_in_list = Column(Boolean, default=True)
    is_displayed_in_card = Column(Boolean, default=True)
    _default_value = Column("default_value", Text)

    # Relationships
    material_type = relationship("MaterialType")
    property = relationship("PropertyDefinition")

    # JSON property handling for SQLite
    @property
    def default_value(self):
        if self._default_value:
            return json.loads(self._default_value)
        return None

    @default_value.setter
    def default_value(self, value):
        if value is not None:
            self._default_value = json.dumps(value)
        else:
            self._default_value = None


class DynamicMaterial(Base, TimestampMixin):
    """
    Material entity with dynamic properties.

    This model represents materials with type-specific dynamic properties
    stored in the material_property_values table.
    """
    __tablename__ = "dynamic_materials"

    id = Column(Integer, primary_key=True, index=True)
    material_type_id = Column(Integer, ForeignKey("material_types.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="in_stock")
    quantity = Column(Float, default=0)
    unit = Column(String(50), nullable=False)
    quality = Column(String(50))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    supplier = Column(String(255))
    sku = Column(String(100))
    description = Column(Text)
    reorder_point = Column(Float, default=0)
    supplier_sku = Column(String(100))
    cost_price = Column(Float)
    price = Column(Float)
    storage_location = Column(String(100))
    notes = Column(Text)
    thumbnail = Column(String(255))

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
        backref="dynamic_materials"
    )
    tags = relationship(
        "Tag",
        secondary="material_tags",
        backref="dynamic_materials"
    )

    @property
    def value(self):
        """Calculate the total cost value of this material in inventory."""
        if self.cost_price is None:
            return None
        return self.quantity * self.cost_price

    @property
    def total_selling_value(self):
        """Calculate the total selling value of this material in inventory."""
        if self.price is None:
            return None
        return self.quantity * self.price


class MaterialPropertyValue(Base):
    """
    Stores the actual values of properties for a specific material.
    Uses polymorphic storage based on data type.
    """
    __tablename__ = "material_property_values"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("dynamic_materials.id", ondelete="CASCADE"), nullable=False)
    property_id = Column(Integer, ForeignKey("property_definitions.id"), nullable=False)

    # Polymorphic storage based on data type
    value_string = Column(Text)
    value_number = Column(Float)
    value_boolean = Column(Boolean)
    value_date = Column(String(50))  # ISO-8601 format
    value_enum_id = Column(Integer)  # Reference to enum value or property_enum_options
    value_file_id = Column(String(100))  # Reference to file/media asset
    value_reference_id = Column(Integer)  # Reference to another entity

    # Relationships
    material = relationship("DynamicMaterial", back_populates="property_values")
    property = relationship("PropertyDefinition")

    __table_args__ = (
        UniqueConstraint('material_id', 'property_id', name='uq_material_property'),
    )