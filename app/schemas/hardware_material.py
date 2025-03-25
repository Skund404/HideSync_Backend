# File: app/schemas/hardware_material.py
"""
Hardware material schemas for the HideSync API.

This module contains Pydantic models specific to hardware materials,
extending the base material schemas with hardware-specific properties.
"""

from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator

from app.schemas.material import MaterialBase, MaterialInDB, MaterialResponse
from app.db.models.enums import (
    MaterialType,
    MaterialStatus,
    MaterialQualityGrade,
    HardwareType,
    HardwareMaterial as HardwareMaterialEnum,
    HardwareFinish,
    MeasurementUnit,
)


class HardwareMaterialBase(MaterialBase):
    """
    Base schema for hardware material data.

    Contains all hardware-specific fields along with common material fields.
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

    class Config:
        from_attributes = True


class HardwareMaterialCreate(HardwareMaterialBase):
    """
    Schema for creating a new hardware material.

    Requires essential fields for hardware material creation.
    """

    name: str = Field(..., description="Name of the hardware material", min_length=1)
    quantity: float = Field(..., description="Initial quantity", ge=0)
    unit: MeasurementUnit = Field(..., description="Unit of measurement")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Brass Buckle - 1.5 inch",
                "material_type": "HARDWARE",
                "hardware_type": "BUCKLE",
                "hardware_material": "BRASS",
                "finish": "ANTIQUE",
                "size": "1.5 inch",
                "color": "Brass",
                "quantity": 50,
                "unit": "PIECE",
                "quality": "STANDARD",
                "reorder_point": 10,
                "cost": 3.50,
                "supplier_id": 2,
                "storage_location": "Drawer B-3"
            }
        }


class HardwareMaterialUpdate(BaseModel):
    """
    Schema for updating hardware material information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the hardware material", min_length=1
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

    hardware_type: Optional[HardwareType] = Field(None, description="Type of hardware")
    hardware_material: Optional[HardwareMaterialEnum] = Field(
        None, description="Material the hardware is made of"
    )
    finish: Optional[HardwareFinish] = Field(None, description="Finish of the hardware")
    size: Optional[str] = Field(None, description="Size specification")
    color: Optional[str] = Field(None, description="Color of the hardware")

    class Config:
        json_schema_extra = {
            "example": {
                "quantity": 25,
                "finish": "POLISHED",
                "reorder_point": 5,
                "notes": "New supplier offers better quality"
            }
        }


class HardwareMaterialInDB(HardwareMaterialBase):
    """
    Schema for hardware material information as stored in the database.

    Includes all fields from the database model.
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


class HardwareMaterialResponse(HardwareMaterialInDB):
    """
    Schema for hardware material responses in the API.

    Includes additional calculated fields.
    """

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


class HardwareMaterialList(BaseModel):
    """
    Schema for paginated hardware material list responses.
    """

    items: List[HardwareMaterialResponse]
    total: int = Field(..., description="Total number of materials matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")