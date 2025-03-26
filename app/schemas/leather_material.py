# File: app/schemas/leather_material.py
"""
Leather material schemas for the HideSync API.

This module contains Pydantic models specific to leather materials,
extending the base material schemas with leather-specific properties.
"""

from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator

from app.schemas.material import MaterialBase, MaterialInDB, MaterialResponse
from app.db.models.enums import (
    MaterialType,
    MaterialStatus,
    MaterialQualityGrade,
    LeatherType,
    LeatherFinish,
    MeasurementUnit,
)


class LeatherMaterialBase(MaterialBase):
    """
    Base schema for leather material data.

    Contains all leather-specific fields along with common material fields.
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

    class Config:
        from_attributes = True


class LeatherMaterialCreate(LeatherMaterialBase):
    """
    Schema for creating a new leather material.

    Requires essential fields for leather material creation.
    """

    name: str = Field(..., description="Name of the leather material", min_length=1)
    quantity: float = Field(..., description="Initial quantity", ge=0)
    unit: MeasurementUnit = Field(..., description="Unit of measurement")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Veg-Tan Shoulder",
                "material_type": "LEATHER",
                "leather_type": "VEGETABLE_TANNED",
                "tannage": "Traditional bark tannage",
                "animal_source": "COWHIDE",
                "thickness": 2.2,
                "area": 12.5,
                "is_full_hide": False,
                "color": "Natural",
                "finish": "NATURAL",
                "grade": "AAA",
                "quantity": 3,
                "unit": "PIECE",
                "quality": "PREMIUM",
                "reorder_point": 1,
                "cost": 120.00,
                "supplier_id": 1,
                "storage_location": "Shelf A-12"
            }
        }


class LeatherMaterialUpdate(BaseModel):
    """
    Schema for updating leather material information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Name of the leather material", min_length=1
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

    class Config:
        json_schema_extra = {
            "example": {
                "thickness": 2.5,
                "color": "Dark Brown",
                "finish": "PULL_UP",
                "quantity": 5.0,
                "notes": "New inventory from recent order"
            }
        }


class LeatherMaterialInDB(LeatherMaterialBase):
    """
    Schema for leather material information as stored in the database.

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


class LeatherMaterialResponse(LeatherMaterialInDB):
    """
    Schema for leather material responses in the API.

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


class LeatherMaterialList(BaseModel):
    """
    Schema for paginated leather material list responses.
    """

    items: List[LeatherMaterialResponse]
    total: int = Field(..., description="Total number of materials matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")