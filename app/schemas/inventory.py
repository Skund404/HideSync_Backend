# File: app/schemas/inventory.py
"""
Inventory schemas for the HideSync API.

This module contains Pydantic models for inventory management, including
inventory items and inventory transactions.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator

from app.db.models.enums import (
    InventoryStatus,
    TransactionType,
    InventoryAdjustmentType,
)


class InventoryBase(BaseModel):
    """
    Base schema for inventory data shared across different operations.
    """

    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    quantity: float = Field(..., description="Available quantity", ge=0)
    status: InventoryStatus = Field(..., description="Current inventory status")
    storage_location: Optional[str] = Field(
        None, description="Storage location identifier"
    )


class InventoryCreate(InventoryBase):
    """
    Schema for creating a new inventory record.
    """

    @validator("item_type")
    def validate_item_type(cls, v):
        valid_types = ["material", "product", "tool"]
        if v.lower() not in valid_types:
            raise ValueError(f"Item type must be one of: {', '.join(valid_types)}")
        return v.lower()


class InventoryUpdate(BaseModel):
    """
    Schema for updating inventory information.

    All fields are optional to allow partial updates.
    """

    quantity: Optional[float] = Field(None, description="Available quantity", ge=0)
    status: Optional[InventoryStatus] = Field(
        None, description="Current inventory status"
    )
    storage_location: Optional[str] = Field(
        None, description="Storage location identifier"
    )


class InventoryInDB(InventoryBase):
    """
    Schema for inventory information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the inventory record")

    class Config:
        from_attributes = True


class InventoryResponse(InventoryInDB):
    """
    Schema for inventory responses in the API.
    """

    item_name: Optional[str] = Field(None, description="Name of the inventoried item")
    value: Optional[float] = Field(
        None, description="Total value of the inventory item"
    )
    is_low_stock: Optional[bool] = Field(
        None, description="Whether the item is in low stock status"
    )
    reorder_point: Optional[float] = Field(
        None, description="Quantity threshold for reordering"
    )
    days_of_supply: Optional[int] = Field(
        None, description="Estimated days until stock depletion"
    )
    storage_location_name: Optional[str] = Field(
        None, description="Name of the storage location"
    )

    class Config:
        from_attributes = True


class InventoryList(BaseModel):
    """
    Schema for paginated inventory list responses.
    """

    items: List[InventoryResponse]
    total: int = Field(
        ..., description="Total number of inventory records matching the query"
    )
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class InventoryTransactionBase(BaseModel):
    """
    Base schema for inventory transaction data.
    """

    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    quantity: float = Field(..., description="Transaction quantity", ge=0)
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    adjustment_type: Optional[InventoryAdjustmentType] = Field(
        None, description="Type of adjustment if transaction_type is ADJUSTMENT"
    )
    reference_id: Optional[str] = Field(
        None, description="Related record ID (e.g., sale, purchase)"
    )
    reference_type: Optional[str] = Field(
        None, description="Type of the related record"
    )
    from_location: Optional[str] = Field(
        None, description="Source location for transfers"
    )
    to_location: Optional[str] = Field(
        None, description="Destination location for transfers"
    )
    notes: Optional[str] = Field(
        None, description="Additional notes about the transaction"
    )


class InventoryTransactionCreate(InventoryTransactionBase):
    """
    Schema for creating a new inventory transaction.
    """

    @validator("adjustment_type")
    def validate_adjustment_type(cls, v, values):
        if values.get("transaction_type") == TransactionType.ADJUSTMENT and v is None:
            raise ValueError("Adjustment type is required for adjustment transactions")
        return v

    @validator("item_type")
    def validate_item_type(cls, v):
        valid_types = ["material", "product", "tool"]
        if v.lower() not in valid_types:
            raise ValueError(f"Item type must be one of: {', '.join(valid_types)}")
        return v.lower()


class InventoryTransactionUpdate(BaseModel):
    """
    Schema for updating inventory transaction information.

    Limited fields are updatable since transactions should be mostly immutable.
    """

    notes: Optional[str] = Field(
        None, description="Additional notes about the transaction"
    )


class InventoryTransactionInDB(InventoryTransactionBase):
    """
    Schema for inventory transaction information as stored in the database.
    """

    id: int = Field(..., description="Unique identifier for the transaction")
    created_at: datetime = Field(
        ..., description="Timestamp when the transaction was created"
    )
    created_by: Optional[str] = Field(
        None, description="User who created the transaction"
    )

    class Config:
        from_attributes = True


class InventoryTransactionResponse(InventoryTransactionInDB):
    """
    Schema for inventory transaction responses in the API.
    """

    item_name: Optional[str] = Field(None, description="Name of the inventoried item")
    from_location_name: Optional[str] = Field(
        None, description="Name of the source location"
    )
    to_location_name: Optional[str] = Field(
        None, description="Name of the destination location"
    )
    reference_name: Optional[str] = Field(
        None, description="Name of the referenced entity"
    )
    value: Optional[float] = Field(
        None, description="Monetary value of the transaction"
    )

    class Config:
        from_attributes = True


class InventoryTransactionList(BaseModel):
    """
    Schema for paginated inventory transaction list responses.
    """

    items: List[InventoryTransactionResponse]
    total: int = Field(
        ..., description="Total number of transactions matching the query"
    )
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class InventorySummary(BaseModel):
    """
    Schema for inventory summary statistics.
    """

    total_items: int = Field(
        ..., description="Total number of unique items in inventory"
    )
    total_value: float = Field(..., description="Total value of all inventory")
    low_stock_items: int = Field(..., description="Number of items in low stock status")
    out_of_stock_items: int = Field(..., description="Number of items out of stock")
    inventory_by_type: Dict[str, int] = Field(..., description="Count of items by type")
    inventory_value_by_type: Dict[str, float] = Field(
        ..., description="Value of inventory by type"
    )
    recent_transactions: List[InventoryTransactionResponse] = Field(
        ..., description="Most recent inventory transactions"
    )


class InventoryAdjustmentRequest(BaseModel):
    """
    Schema for inventory adjustment requests.
    """

    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    quantity: float = Field(
        ...,
        description="Adjustment quantity (positive for increase, negative for decrease)",
    )
    adjustment_type: InventoryAdjustmentType = Field(
        ..., description="Type of adjustment"
    )
    reason: str = Field(..., description="Reason for the adjustment")
    notes: Optional[str] = Field(None, description="Additional notes")


class InventoryTransferRequest(BaseModel):
    """
    Schema for inventory transfer requests.
    """

    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    quantity: float = Field(..., description="Quantity to transfer", gt=0)
    from_location: str = Field(..., description="Source location ID")
    to_location: str = Field(..., description="Destination location ID")
    notes: Optional[str] = Field(None, description="Additional notes")


class InventoryCountRequest(BaseModel):
    """
    Schema for inventory count/reconciliation requests.
    """

    items: List[Dict[str, Any]] = Field(
        ..., description="List of items and their counted quantities"
    )
    count_date: datetime = Field(..., description="Date and time of the count")
    count_type: str = Field(..., description="Type of count (cycle, annual, spot)")
    location: Optional[str] = Field(
        None, description="Location where the count was performed"
    )
    counted_by: Optional[str] = Field(None, description="User who performed the count")
    notes: Optional[str] = Field(None, description="Additional notes")


# Add these classes at the end of your existing inventory.py file:


# Add this class to match what the endpoint is looking for
class Inventory(InventoryResponse):
    """
    Schema for inventory responses in the API.
    This is an alias of InventoryResponse for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class InventoryTransaction(InventoryTransactionResponse):
    """
    Schema for inventory transaction responses in the API.
    This is an alias of InventoryTransactionResponse for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class InventorySearchParams(BaseModel):
    """
    Schema for inventory search parameters.
    """

    status: Optional[str] = None
    location: Optional[str] = None
    item_type: Optional[str] = None
    search: Optional[str] = None


# Add this class for the endpoint
class InventoryAdjustment(InventoryAdjustmentRequest):
    """
    Schema for inventory adjustment.
    This is an alias of InventoryAdjustmentRequest for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class StockLevelReport(BaseModel):
    """
    Stock level report model.
    """

    total_value: float
    category_breakdown: Dict[str, Any]
    low_stock_items: List[Inventory]
    out_of_stock_items: List[Inventory]
    items_by_location: Dict[str, int]
    reorder_recommendations: List[Dict[str, Any]]


# Add these classes at the end of your existing inventory.py file:


# Add this class to match what the endpoint is looking for
class Inventory(InventoryResponse):
    """
    Schema for inventory responses in the API.
    This is an alias of InventoryResponse for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class InventoryTransaction(InventoryTransactionResponse):
    """
    Schema for inventory transaction responses in the API.
    This is an alias of InventoryTransactionResponse for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class InventorySearchParams(BaseModel):
    """
    Schema for inventory search parameters.
    """

    status: Optional[str] = None
    location: Optional[str] = None
    item_type: Optional[str] = None
    search: Optional[str] = None


# Add this class for the endpoint
class InventoryAdjustment(InventoryAdjustmentRequest):
    """
    Schema for inventory adjustment.
    This is an alias of InventoryAdjustmentRequest for compatibility with endpoint imports.
    """

    pass


# Add this class for the endpoint
class StockLevelReport(BaseModel):
    """
    Stock level report model.
    """

    total_value: float
    category_breakdown: Dict[str, Any]
    low_stock_items: List[Inventory]
    out_of_stock_items: List[Inventory]
    items_by_location: Dict[str, int]
    reorder_recommendations: List[Dict[str, Any]]
