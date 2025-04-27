# app/schemas/dynamic_material.py

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


# --- PropertyDefinition Schemas ---

class PropertyEnumOptionBase(BaseModel):
    """Base schema for property enum options."""
    value: str = Field(..., description="Unique value code for the option")
    display_value: str = Field(..., description="Display text for the option")
    color: Optional[str] = Field(None, description="Optional color code for the option")
    display_order: Optional[int] = Field(None, description="Order for displaying options")


class PropertyEnumOptionCreate(PropertyEnumOptionBase):
    """Schema for creating a new property enum option."""
    pass


class PropertyEnumOptionRead(PropertyEnumOptionBase):
    """Schema for reading a property enum option."""
    id: int = Field(..., description="Unique identifier")

    class Config:
        orm_mode = True


class PropertyDefinitionTranslation(BaseModel):
    """Schema for property definition translation."""
    display_name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class PropertyDefinitionBase(BaseModel):
    """Base schema for property definitions."""
    name: str = Field(..., description="Unique name for the property", regex=r"^[a-zA-Z0-9_]+$")
    data_type: str = Field(..., description="Data type (string, number, boolean, enum, date, reference, file)")
    group_name: Optional[str] = Field(None, description="Optional group name for organizing properties")
    unit: Optional[str] = Field(None, description="Optional unit of measurement")
    is_required: Optional[bool] = Field(False, description="Whether this property is required")
    has_multiple_values: Optional[bool] = Field(False, description="Whether this property can have multiple values")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Optional validation rules")

    @validator('data_type')
    def validate_data_type(cls, v):
        valid_types = ['string', 'number', 'boolean', 'enum', 'date', 'reference', 'file']
        if v not in valid_types:
            raise ValueError(f"data_type must be one of: {', '.join(valid_types)}")
        return v


class PropertyDefinitionCreate(PropertyDefinitionBase):
    """Schema for creating a new property definition."""
    translations: Optional[Dict[str, PropertyDefinitionTranslation]] = Field(
        {}, description="Translations keyed by locale code"
    )
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for enum properties")
    enum_options: Optional[List[PropertyEnumOptionCreate]] = Field(None, description="Custom enum options")

    @validator('enum_options', 'enum_type_id')
    def validate_enum_config(cls, v, values):
        data_type = values.get('data_type')
        if data_type == 'enum':
            # For enum type, need either enum_type_id or enum_options
            if v is None and values.get('enum_type_id') is None and values.get('enum_options') is None:
                raise ValueError("Either enum_type_id or enum_options must be provided for enum properties")
        elif v is not None:
            # Non-enum properties should not have enum config
            raise ValueError(f"enum_options or enum_type_id can only be used with enum data_type")
        return v


class PropertyDefinitionUpdate(BaseModel):
    """Schema for updating a property definition."""
    group_name: Optional[str] = Field(None, description="Optional group name for organizing properties")
    unit: Optional[str] = Field(None, description="Optional unit of measurement")
    is_required: Optional[bool] = Field(None, description="Whether this property is required")
    has_multiple_values: Optional[bool] = Field(None, description="Whether this property can have multiple values")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Optional validation rules")
    translations: Optional[Dict[str, PropertyDefinitionTranslation]] = Field(
        None, description="Translations keyed by locale code"
    )
    enum_options: Optional[List[PropertyEnumOptionCreate]] = Field(None, description="Custom enum options")


class PropertyDefinitionRead(PropertyDefinitionBase):
    """Schema for reading a property definition."""
    id: int = Field(..., description="Unique identifier")
    translations: Dict[str, PropertyDefinitionTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for enum properties")
    enum_options: List[PropertyEnumOptionRead] = Field([], description="Custom enum options")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_system: bool = Field(False, description="Whether this is a system property")

    class Config:
        orm_mode = True


# --- MaterialType Schemas ---

class MaterialTypePropertyBase(BaseModel):
    """Schema for material type property assignments."""
    property_id: int = Field(..., description="ID of the property")
    display_order: Optional[int] = Field(None, description="Order for displaying the property")
    is_required: Optional[bool] = Field(False, description="Whether the property is required for this material type")
    is_filterable: Optional[bool] = Field(True, description="Whether the property can be used for filtering")
    is_displayed_in_list: Optional[bool] = Field(True, description="Whether to display the property in list views")
    is_displayed_in_card: Optional[bool] = Field(True, description="Whether to display the property in card views")
    default_value: Optional[Any] = Field(None, description="Default value for the property")
    enum_options: Optional[List[PropertyEnumOptionCreate]] = Field(None,
                                                                   description="Custom enum options for this property")
    enum_type_id: Optional[int] = Field(None, description="ID of the enum type for this property")


class MaterialTypeTranslation(BaseModel):
    """Schema for material type translation."""
    display_name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class MaterialTypeBase(BaseModel):
    """Base schema for material types."""
    name: str = Field(..., description="Unique name for the material type", regex=r"^[a-zA-Z0-9_]+$")
    icon: Optional[str] = Field(None, description="Icon identifier or path")
    color_scheme: Optional[str] = Field(None, description="Color scheme for UI")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration as JSON")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage configuration as JSON")
    visibility_level: Optional[str] = Field("all", description="Visibility level (all, admin, specific tier)")


class MaterialTypeCreate(MaterialTypeBase):
    """Schema for creating a new material type."""
    translations: Dict[str, MaterialTypeTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    properties: List[MaterialTypePropertyBase] = Field(
        [], description="Properties assigned to this material type"
    )


class MaterialTypeUpdate(BaseModel):
    """Schema for updating a material type."""
    icon: Optional[str] = Field(None, description="Icon identifier or path")
    color_scheme: Optional[str] = Field(None, description="Color scheme for UI")
    ui_config: Optional[Dict[str, Any]] = Field(None, description="UI configuration as JSON")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage configuration as JSON")
    visibility_level: Optional[str] = Field(None, description="Visibility level (all, admin, specific tier)")
    translations: Optional[Dict[str, MaterialTypeTranslation]] = Field(
        None, description="Translations keyed by locale code"
    )
    properties: Optional[List[MaterialTypePropertyBase]] = Field(
        None, description="Properties assigned to this material type"
    )


class MaterialTypeRead(MaterialTypeBase):
    """Schema for reading a material type."""
    id: int = Field(..., description="Unique identifier")
    translations: Dict[str, MaterialTypeTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    properties: List[Dict[str, Any]] = Field(
        [], description="Properties assigned to this material type"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_system: bool = Field(False, description="Whether this is a system material type")

    class Config:
        orm_mode = True


class MaterialTypeImportExport(MaterialTypeBase):
    """Schema for importing/exporting material types."""
    translations: Dict[str, MaterialTypeTranslation] = Field(
        {}, description="Translations keyed by locale code"
    )
    properties: List[MaterialTypePropertyBase] = Field(
        [], description="Properties assigned to this material type"
    )


# --- Material Schemas ---

class MaterialPropertyValueBase(BaseModel):
    """Base schema for material property values."""
    property_id: int = Field(..., description="ID of the property")
    value: Any = Field(None, description="Value of the property")


class MaterialPropertyValueCreate(MaterialPropertyValueBase):
    """Schema for creating a material property value."""
    pass


class MaterialPropertyValueRead(MaterialPropertyValueBase):
    """Schema for reading a material property value."""
    id: int = Field(..., description="Unique identifier")
    property: Dict[str, Any] = Field(..., description="Property definition")

    class Config:
        orm_mode = True


class DynamicMaterialBase(BaseModel):
    """Base schema for dynamic materials."""
    material_type_id: int = Field(..., description="ID of the material type")
    name: str = Field(..., description="Name of the material")
    status: Optional[str] = Field("in_stock", description="Inventory status")
    quantity: Optional[float] = Field(0, description="Current quantity", ge=0)
    unit: str = Field(..., description="Unit of measurement")
    quality: Optional[str] = Field(None, description="Quality grade")
    supplier_id: Optional[int] = Field(None, description="ID of the supplier")
    supplier: Optional[str] = Field(None, description="Name of the supplier")
    sku: Optional[str] = Field(None, description="Stock keeping unit")
    description: Optional[str] = Field(None, description="Description")
    reorder_point: Optional[float] = Field(0, description="Quantity threshold for reordering", ge=0)
    supplier_sku: Optional[str] = Field(None, description="Supplier's SKU")
    cost_price: Optional[float] = Field(None, description="Cost per unit", ge=0)
    price: Optional[float] = Field(None, description="Selling price per unit", ge=0)
    storage_location: Optional[str] = Field(None, description="Storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    thumbnail: Optional[str] = Field(None, description="URL or path to thumbnail image")


class DynamicMaterialCreate(DynamicMaterialBase):
    """Schema for creating a dynamic material."""
    property_values: List[MaterialPropertyValueCreate] = Field(
        [], description="Property values for this material"
    )
    tag_ids: Optional[List[str]] = Field(None, description="IDs of tags to apply")
    media_ids: Optional[List[str]] = Field(None, description="IDs of media assets to attach")


class DynamicMaterialUpdate(BaseModel):
    """Schema for updating a dynamic material."""
    name: Optional[str] = Field(None, description="Name of the material")
    status: Optional[str] = Field(None, description="Inventory status")
    quantity: Optional[float] = Field(None, description="Current quantity", ge=0)
    unit: Optional[str] = Field(None, description="Unit of measurement")
    quality: Optional[str] = Field(None, description="Quality grade")
    supplier_id: Optional[int] = Field(None, description="ID of the supplier")
    supplier: Optional[str] = Field(None, description="Name of the supplier")
    sku: Optional[str] = Field(None, description="Stock keeping unit")
    description: Optional[str] = Field(None, description="Description")
    reorder_point: Optional[float] = Field(None, description="Quantity threshold for reordering", ge=0)
    supplier_sku: Optional[str] = Field(None, description="Supplier's SKU")
    cost_price: Optional[float] = Field(None, description="Cost per unit", ge=0)
    price: Optional[float] = Field(None, description="Selling price per unit", ge=0)
    storage_location: Optional[str] = Field(None, description="Storage location")
    notes: Optional[str] = Field(None, description="Additional notes")
    thumbnail: Optional[str] = Field(None, description="URL or path to thumbnail image")
    property_values: Optional[List[MaterialPropertyValueCreate]] = Field(
        None, description="Property values for this material"
    )
    tag_ids: Optional[List[str]] = Field(None, description="IDs of tags to apply")
    media_ids: Optional[List[str]] = Field(None, description="IDs of media assets to attach")


class DynamicMaterialRead(DynamicMaterialBase):
    """Schema for reading a dynamic material."""
    id: int = Field(..., description="Unique identifier")
    material_type: Dict[str, Any] = Field(..., description="Material type")
    property_values: List[Dict[str, Any]] = Field([], description="Property values")
    tags: List[Dict[str, Any]] = Field([], description="Tags applied to this material")
    media: List[Dict[str, Any]] = Field([], description="Media attachments")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    inventory_value: Optional[float] = Field(None, description="Total inventory value (quantity * cost_price)")
    total_selling_value: Optional[float] = Field(None, description="Total selling value (quantity * price)")

    class Config:
        orm_mode = True


class DynamicMaterialList(BaseModel):
    """Schema for paginated material list."""
    items: List[DynamicMaterialRead] = Field(..., description="List of materials")
    total: int = Field(..., description="Total number of materials matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")