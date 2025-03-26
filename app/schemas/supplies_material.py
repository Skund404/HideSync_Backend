# File: app/schemas/supplies_material.py
"""
Supplies material schemas for the HideSync API.

This module contains Pydantic models specific to supplies materials,
extending the base material schemas with supplies-specific properties.
"""

from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator

from app.schemas.material import MaterialBase, MaterialInDB, MaterialResponse
from app.db.models.enums import (
    MaterialType,
    MaterialStatus,
    MaterialQualityGrade,
    MeasurementUnit,
)


class SuppliesMaterialBase(MaterialBase):
    """
    Base schema for supplies material data.

    Contains all supplies-specific fields along with common material fields.
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
    supplies_finish: Optional[str] = Field(None, description="Finish characteristics")

    class Config:
        from_attributes = True


class SuppliesMaterialCreate(SuppliesMaterialBase):
    """
    Schema for creating a new supplies material.

    Requires essential fields for supplies material creation.
    """

    name: str = Field(..., description="Name of the supplies material", min_length=1)
    quantity: float = Field(..., description="Initial quantity", ge=0)
    unit: MeasurementUnit = Field(..., description="Unit of measurement")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Waxed Thread - 0.8mm",
                "material_type": "SUPPLIES",
                "supplies_material_type": "THREAD",
                "color": "Dark Brown",
                "thread_thickness": "0.8mm",
                "material_composition": "Polyester",
                "length": 500,
                "quantity": 5,
                "unit": "SPOOL",
                "quality": "PREMIUM",
                "reorder_point": 1,
                "cost": 15.00,
                "supplier_id": 3,
                "storage_location": "Cabinet C-2"
            }
        }


class SuppliesMaterialUpdate(BaseModel):
    """
    Schema for updating supplies material information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the supplies material", min_length=1
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
    supplies_finish: Optional[str] = Field(None, description="Finish characteristics")

    class Config:
        json_schema_extra = {
            "example": {
                "quantity": 10,
                "color": "Black",
                "reorder_point": 2,
                "notes": "Higher demand for this color"
            }
        }


class SuppliesMaterialInDB(SuppliesMaterialBase):
    """
    Schema for supplies material information as stored in the database.

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


class SuppliesMaterialResponse(SuppliesMaterialInDB):
    """
    Schema for supplies material responses in the API.

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


class SuppliesMaterialList(BaseModel):
    """
    Schema for paginated supplies material list responses.
    """

    items: List[SuppliesMaterialResponse]
    total: int = Field(..., description="Total number of materials matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")