# File: app/schemas/material.py
"""
Material schemas for the HideSync API.

This module contains Pydantic models for materials management, including the base
Material schema and specialized schemas for leather, hardware, and supplies materials.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any, ForwardRef, Literal
from pydantic import BaseModel, Field, validator, root_validator, RootModel

from app.db.models.enums import (
    MaterialType,
    MaterialStatus,
    MaterialQualityGrade,
    LeatherType,
    LeatherFinish,
    HardwareType,
    HardwareMaterialEnum,
    HardwareFinish,
    MeasurementUnit,
)

from pydantic import root_validator


class EnumCompatMixin:
    """Mixin to handle enum compatibility issues in response models."""

    # This validator will fix enum issues with responses
    @root_validator(pre=True)
    def fix_enum_fields(cls, values):
        """Process the input values to fix common enum serialization issues."""
        # Create a new dict to avoid modifying the input
        fixed_values = dict(values)

        # Fields to check for enum-like values
        enum_fields = ['status', 'unit', 'material_type', 'quality']

        for field in enum_fields:
            if field in fixed_values:
                value = fixed_values[field]

                # Skip None values
                if value is None:
                    continue

                # Handle tuples (most common issue)
                if isinstance(value, tuple) and len(value) == 1:
                    fixed_values[field] = value[0]

                # Handle objects with value attribute (Enum objects)
                elif hasattr(value, 'value'):
                    fixed_values[field] = value.value

        # Ensure timestamps exist
        if 'created_at' in fixed_values and fixed_values['created_at'] is None:
            fixed_values['created_at'] = datetime.utcnow()

        if 'updated_at' in fixed_values and fixed_values['updated_at'] is None:
            fixed_values['updated_at'] = datetime.utcnow()

        return fixed_values


class MaterialBase(BaseModel):
    """
    Base schema for material data shared across different operations.

    Contains common fields used across all material types.
    """

    name: str = Field(
        ..., description="Name of the material", min_length=1, max_length=100
    )
    status: Optional[MaterialStatus] = Field(
        MaterialStatus.IN_STOCK, description="Current inventory status"
    )
    quantity: float = Field(..., description="Available quantity", ge=0)
    unit: MeasurementUnit = Field(..., description="Unit of measurement")
    quality: Optional[MaterialQualityGrade] = Field(
        None, description="Quality grade of the material"
    )
    supplier_id: Optional[int] = Field(None, description="ID of the supplier")
    supplier: Optional[str] = Field(None, description="Name of the supplier")
    sku: Optional[str] = Field(None, description="Stock keeping unit identifier")
    description: Optional[str] = Field(None, description="Detailed description")
    reorder_point: Optional[float] = Field(
        None, description="Quantity threshold for reordering", ge=0
    )
    supplier_sku: Optional[str] = Field(
        None, description="Supplier's SKU for this material"
    )
    cost: Optional[float] = Field(None, description="Cost per unit", ge=0)
    price: Optional[float] = Field(
        None, description="Selling price per unit if applicable", ge=0
    )
    storage_location: Optional[str] = Field(
        None, description="Location where the material is stored"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    thumbnail: Optional[str] = Field(None, description="URL or path to thumbnail image")
    material_type: MaterialType = Field(
        ..., description="Type of material (LEATHER, HARDWARE, SUPPLIES)"
    )


class LeatherMaterialBase(MaterialBase):
    """
    Base schema for leather materials.
    """

    material_type: Literal[MaterialType.LEATHER] = Field(
        MaterialType.LEATHER, description="Type of material"
    )
    leather_type: Optional[LeatherType] = Field(None, description="Type of leather")
    tannage: Optional[str] = Field(None, description="Tanning method")
    animal_source: Optional[str] = Field(None, description="Source animal")
    thickness: Optional[float] = Field(None, description="Thickness in mm", gt=0)
    area: Optional[float] = Field(None, description="Area in square units", gt=0)
    is_full_hide: Optional[bool] = Field(
        False, description="Whether this is a full hide"
    )
    color: Optional[str] = Field(None, description="Color of the leather")
    finish: Optional[LeatherFinish] = Field(
        None, description="Finish applied to the leather"
    )
    grade: Optional[str] = Field(None, description="Quality grade specific to leather")


class HardwareMaterialBase(MaterialBase):
    """
    Base schema for hardware materials.
    """

    material_type: Literal[MaterialType.HARDWARE] = Field(
        MaterialType.HARDWARE, description="Type of material"
    )
    hardware_type: Optional[HardwareType] = Field(None, description="Type of hardware")
    hardware_material: Optional[HardwareMaterialEnum] = Field(
        None, description="Material the hardware is made of"
    )
    finish: Optional[HardwareFinish] = Field(None, description="Finish of the hardware")
    size: Optional[str] = Field(None, description="Size specification")
    color: Optional[str] = Field(None, description="Color of the hardware")


class SuppliesMaterialBase(MaterialBase):
    """
    Base schema for supplies materials.
    """

    material_type: Literal[MaterialType.SUPPLIES] = Field(
        MaterialType.SUPPLIES, description="Type of material"
    )
    supplies_material_type: Optional[str] = Field(
        None, description="Specific type of supplies"
    )
    color: Optional[str] = Field(None, description="Color if applicable")
    thread_thickness: Optional[str] = Field(None, description="Thickness for thread")
    material_composition: Optional[str] = Field(
        None, description="What the supply is made of"
    )
    volume: Optional[float] = Field(
        None, description="Volume for liquid supplies", gt=0
    )
    length: Optional[float] = Field(
        None, description="Length for linear supplies", gt=0
    )
    drying_time: Optional[str] = Field(
        None, description="Drying time for adhesives/finishes"
    )
    application_method: Optional[str] = Field(
        None, description="How to apply the material"
    )
    finish: Optional[str] = Field(None, description="Finish characteristics")


MaterialCreate = RootModel[
    Union[LeatherMaterialBase, HardwareMaterialBase, SuppliesMaterialBase]
]
"""
Schema for creating a new material.
This is a union type that allows creating any of the specialized material types.
"""


class LeatherMaterialCreate(LeatherMaterialBase):
    """Schema for creating a new leather material."""

    pass


class HardwareMaterialCreate(HardwareMaterialBase):
    """Schema for creating a new hardware material."""

    pass


class SuppliesMaterialCreate(SuppliesMaterialBase):
    """Schema for creating a new supplies material."""

    pass


class MaterialUpdate(BaseModel):
    """
    Schema for updating material information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the material", min_length=1, max_length=100
    )
    status: Optional[MaterialStatus] = Field(
        None, description="Current inventory status"
    )
    quantity: Optional[float] = Field(None, description="Available quantity", ge=0)
    unit: Optional[MeasurementUnit] = Field(None, description="Unit of measurement")
    quality: Optional[MaterialQualityGrade] = Field(
        None, description="Quality grade of the material"
    )
    supplier_id: Optional[int] = Field(None, description="ID of the supplier")
    supplier: Optional[str] = Field(None, description="Name of the supplier")
    sku: Optional[str] = Field(None, description="Stock keeping unit identifier")
    description: Optional[str] = Field(None, description="Detailed description")
    reorder_point: Optional[float] = Field(
        None, description="Quantity threshold for reordering", ge=0
    )
    supplier_sku: Optional[str] = Field(
        None, description="Supplier's SKU for this material"
    )
    cost: Optional[float] = Field(None, description="Cost per unit", ge=0)
    price: Optional[float] = Field(
        None, description="Selling price per unit if applicable", ge=0
    )
    storage_location: Optional[str] = Field(
        None, description="Location where the material is stored"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    thumbnail: Optional[str] = Field(None, description="URL or path to thumbnail image")


class LeatherMaterialUpdate(MaterialUpdate):
    """
    Schema for updating leather material information.
    """

    leather_type: Optional[LeatherType] = Field(None, description="Type of leather")
    tannage: Optional[str] = Field(None, description="Tanning method")
    animal_source: Optional[str] = Field(None, description="Source animal")
    thickness: Optional[float] = Field(None, description="Thickness in mm", gt=0)
    area: Optional[float] = Field(None, description="Area in square units", gt=0)
    is_full_hide: Optional[bool] = Field(
        None, description="Whether this is a full hide"
    )
    color: Optional[str] = Field(None, description="Color of the leather")
    finish: Optional[LeatherFinish] = Field(
        None, description="Finish applied to the leather"
    )
    grade: Optional[str] = Field(None, description="Quality grade specific to leather")


class HardwareMaterialUpdate(MaterialUpdate):
    """
    Schema for updating hardware material information.
    """

    hardware_type: Optional[HardwareType] = Field(None, description="Type of hardware")
    hardware_material: Optional[HardwareMaterialEnum] = Field(
        None, description="Material the hardware is made of"
    )
    finish: Optional[HardwareFinish] = Field(None, description="Finish of the hardware")
    size: Optional[str] = Field(None, description="Size specification")
    color: Optional[str] = Field(None, description="Color of the hardware")


class SuppliesMaterialUpdate(MaterialUpdate):
    """
    Schema for updating supplies material information.
    """

    supplies_material_type: Optional[str] = Field(
        None, description="Specific type of supplies"
    )
    color: Optional[str] = Field(None, description="Color if applicable")
    thread_thickness: Optional[str] = Field(None, description="Thickness for thread")
    material_composition: Optional[str] = Field(
        None, description="What the supply is made of"
    )
    volume: Optional[float] = Field(
        None, description="Volume for liquid supplies", gt=0
    )
    length: Optional[float] = Field(
        None, description="Length for linear supplies", gt=0
    )
    drying_time: Optional[str] = Field(
        None, description="Drying time for adhesives/finishes"
    )
    application_method: Optional[str] = Field(
        None, description="How to apply the material"
    )
    finish: Optional[str] = Field(None, description="Finish characteristics")


class MaterialInDB(MaterialBase):
    """
    Schema for material information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the material")
    created_at: datetime = Field(
        ..., description="Timestamp when the material was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the material was last updated"
    )

    class Config:
        from_attributes = True


class LeatherMaterialInDB(LeatherMaterialBase, MaterialInDB):
    """
    Schema for leather material information as stored in the database.
    """

    class Config:
        from_attributes = True


class HardwareMaterialInDB(HardwareMaterialBase, MaterialInDB):
    """
    Schema for hardware material information as stored in the database.
    """

    class Config:
        from_attributes = True


class SuppliesMaterialInDB(SuppliesMaterialBase, MaterialInDB):
    """
    Schema for supplies material information as stored in the database.
    """

    class Config:
        from_attributes = True


class MaterialResponse(MaterialInDB, EnumCompatMixin):
    """Schema for material responses in the API."""

    inventory_value: Optional[float] = Field(
        None, description="Total value of inventory (quantity × cost)"
    )
    days_since_last_purchase: Optional[int] = Field(
        None, description="Days since last purchase"
    )
    is_low_stock: Optional[bool] = Field(
        None, description="Whether the material is below reorder point"
    )

    class Config:
        from_attributes = True


class LeatherMaterialResponse(LeatherMaterialInDB, EnumCompatMixin):
    """Schema for leather material responses in the API."""

    inventory_value: Optional[float] = Field(
        None, description="Total value of inventory (quantity × cost)"
    )
    days_since_last_purchase: Optional[int] = Field(
        None, description="Days since last purchase"
    )
    is_low_stock: Optional[bool] = Field(
        None, description="Whether the material is below reorder point"
    )

    class Config:
        from_attributes = True


class HardwareMaterialResponse(HardwareMaterialInDB, EnumCompatMixin):
    """Schema for hardware material responses in the API."""

    inventory_value: Optional[float] = Field(
        None, description="Total value of inventory (quantity × cost)"
    )
    days_since_last_purchase: Optional[int] = Field(
        None, description="Days since last purchase"
    )
    is_low_stock: Optional[bool] = Field(
        None, description="Whether the material is below reorder point"
    )

    class Config:
        from_attributes = True


class SuppliesMaterialResponse(SuppliesMaterialInDB, EnumCompatMixin):
    """Schema for supplies material responses in the API."""

    inventory_value: Optional[float] = Field(
        None, description="Total value of inventory (quantity × cost)"
    )
    days_since_last_purchase: Optional[int] = Field(
        None, description="Days since last purchase"
    )
    is_low_stock: Optional[bool] = Field(
        None, description="Whether the material is below reorder point"
    )

    class Config:
        from_attributes = True


class MaterialList(BaseModel):
    """
    Schema for paginated material list responses.
    """

    items: List[MaterialResponse]
    total: int = Field(..., description="Total number of materials matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class MaterialSearchParams(BaseModel):
    material_type: Optional[str] = None
    quality: Optional[str] = None
    in_stock: Optional[bool] = None
    search: Optional[str] = None
