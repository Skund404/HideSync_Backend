# File: app/schemas/inventory.py
"""
Inventory schemas for the HideSync API.

This module contains Pydantic models for inventory management, including
inventory items, transactions, requests, and reports.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator

# Assuming enums are correctly defined here
from app.db.models.enums import (
    InventoryStatus,
    TransactionType,
    InventoryAdjustmentType,
)


# --- Base Schemas ---

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


class InventoryTransactionBase(BaseModel):
    """
    Base schema for inventory transaction data.
    """
    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    # Changed quantity to quantity_change for clarity in transactions
    quantity_change: float = Field(..., description="Quantity changed in this transaction (+/-)")
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


# --- Create Schemas ---

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


# --- Update Schemas ---

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


class InventoryTransactionUpdate(BaseModel):
    """
    Schema for updating inventory transaction information.
    Limited fields are updatable since transactions should be mostly immutable.
    """
    notes: Optional[str] = Field(
        None, description="Additional notes about the transaction"
    )


# --- Database Schemas ---

class InventoryInDB(InventoryBase):
    """
    Schema for inventory information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the inventory record")

    class Config:
        from_attributes = True


class InventoryTransactionInDB(InventoryTransactionBase):
    """
    Schema for inventory transaction information as stored in the database.
    """
    id: int = Field(..., description="Unique identifier for the transaction")
    # Renamed created_at to transaction_date for clarity
    transaction_date: datetime = Field(
        ..., description="Timestamp when the transaction occurred"
    )
    created_by: Optional[str] = Field(
        None, description="User who created the transaction"
    )

    class Config:
        from_attributes = True


# --- API Response Schemas ---

class InventoryResponse(InventoryInDB):
    """
    Schema for inventory responses in the API. Includes derived fields.
    """
    item_name: Optional[str] = Field(None, description="Name of the inventoried item")
    value: Optional[float] = Field(
        None, description="Estimated total value of the current stock"
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


class InventoryTransactionResponse(InventoryTransactionInDB):
    """
    Schema for inventory transaction responses in the API. Includes derived fields.
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
    value_change: Optional[float] = Field(
        None, description="Estimated monetary value change of this transaction"
    )

    class Config:
        from_attributes = True


# --- List Response Schemas ---

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


# --- Specific Request/Report Schemas ---

class InventorySearchParams(BaseModel):
    """
    Schema for inventory search parameters used in API requests.
    """
    status: Optional[str] = None
    location: Optional[str] = None
    item_type: Optional[str] = None
    search: Optional[str] = None


class InventoryAdjustmentRequest(BaseModel):
    """
    Schema for inventory adjustment requests via the API.
    """
    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    # Renamed quantity to quantity_change for clarity
    quantity_change: float = Field(
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
    Schema for inventory transfer requests via the API.
    """
    item_type: str = Field(..., description="Type of item (material, product, tool)")
    item_id: int = Field(..., description="ID of the item")
    quantity: float = Field(..., description="Quantity to transfer", gt=0)
    from_location: str = Field(..., description="Source location ID")
    to_location: str = Field(..., description="Destination location ID")
    notes: Optional[str] = Field(None, description="Additional notes")


class InventoryCountRequest(BaseModel):
    """
    Schema for inventory count/reconciliation requests via the API.
    """
    items: List[Dict[str, Any]] = Field(
        ..., description="List of items and their counted quantities. Expected keys: 'item_type', 'item_id', 'counted_quantity'"
    )
    count_date: datetime = Field(..., description="Date and time of the count")
    count_type: str = Field(..., description="Type of count (e.g., 'Cycle', 'Annual', 'Spot')")
    location: Optional[str] = Field(
        None, description="Location identifier where the count was performed"
    )
    counted_by: Optional[str] = Field(None, description="User or identifier of who performed the count")
    notes: Optional[str] = Field(None, description="Additional notes about the count")


class StockLevelReport(BaseModel):
    """
    Schema for the stock level report response.
    """
    report_type: str = Field("stock_level", description="Type of the report")
    generated_at: datetime = Field(..., description="Timestamp when the report was generated")
    filters_applied: Dict[str, Any] = Field(..., description="Filters used for this report")
    total_value: float = Field(..., description="Total estimated value of reported inventory")
    category_breakdown: Dict[str, Any] = Field(..., description="Breakdown by specified category (e.g., type, location)")
    # Using InventoryResponse for consistency
    low_stock_items: List[InventoryResponse] = Field(..., description="Items below their reorder point")
    out_of_stock_items: List[InventoryResponse] = Field(..., description="Items with zero or negative quantity")
    items_by_location: Dict[str, int] = Field(..., description="Count of distinct items per location")
    reorder_recommendations: List[Dict[str, Any]] = Field(..., description="Suggested items and quantities to reorder")


class InventorySummary(BaseModel):
    """
    Schema for inventory summary statistics response.
    """
    generated_at: datetime = Field(..., description="Timestamp when the summary was generated")
    total_items: int = Field(
        ..., description="Total number of unique items tracked in inventory"
    )
    total_value: float = Field(..., description="Total estimated value of all inventory")
    low_stock_items_count: int = Field(..., description="Number of distinct items in low stock status")
    out_of_stock_items_count: int = Field(..., description="Number of distinct items out of stock")
    inventory_by_type: Dict[str, int] = Field(..., description="Count of distinct items by type")
    inventory_value_by_type: Dict[str, float] = Field(
        ..., description="Estimated value of inventory by type"
    )
    # Consider limiting the number of recent transactions shown
    recent_transactions: List[InventoryTransactionResponse] = Field(
        ..., description="A list of the most recent inventory transactions"
    )


# --- Aliases for Endpoint Compatibility ---
# These aliases maintain compatibility with the current endpoint imports.
# Consider updating endpoints to use the more specific schema names directly later.

class Inventory(InventoryResponse):
    """Alias for InventoryResponse used in endpoint response_model."""
    pass

class InventoryTransaction(InventoryTransactionResponse):
    """Alias for InventoryTransactionResponse used in endpoint response_model."""
    pass

class InventoryAdjustment(InventoryAdjustmentRequest):
    """Alias for InventoryAdjustmentRequest used as endpoint input."""
    pass

# InventorySearchParams is defined above and used directly.
# StockLevelReport is defined above and used directly.