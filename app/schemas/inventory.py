# File: app/schemas/inventory.py
"""
Inventory schemas for the HideSync API.

Contains Pydantic models for Inventory items (stock tracking),
Inventory Transactions (movement logs), related requests (adjustments, transfers),
search parameters, reports, and general inventory summaries.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator, field_validator # Use field_validator for Pydantic v2

# Assuming enums are correctly defined in app.db.models.enums
from app.db.models.enums import (
    InventoryAdjustmentType,
    InventoryStatus,
    ProjectType, # Need this if filtering by product type happens here
    TransactionType,
)

# --- Base Schemas ---

class InventoryBase(BaseModel):
    """Base for Inventory data, used for creation and reading."""
    item_type: str = Field(..., description="Type of item ('product', 'material', 'tool').", examples=["product"])
    item_id: int = Field(..., description="ID of the related Product, Material, or Tool.", examples=[101])
    quantity: float = Field(..., description="Current quantity on hand.", ge=0.0, examples=[25.5])
    status: InventoryStatus = Field(..., description="Current inventory status (e.g., IN_STOCK).", examples=["IN_STOCK"])
    storage_location: Optional[str] = Field(None, description="Identifier for the storage location.", examples=["Shelf A1"])

    # Pydantic v2 style validator
    @field_validator('item_type')
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        valid_types = ["material", "product", "tool"]
        if v.lower() not in valid_types:
            raise ValueError(f"Item type must be one of: {', '.join(valid_types)}")
        return v.lower()


class InventoryTransactionBase(BaseModel):
    """Base for Inventory Transaction data."""
    item_type: str = Field(..., description="Type of item ('product', 'material', 'tool').", examples=["material"])
    item_id: int = Field(..., description="ID of the related item.", examples=[55])
    quantity_change: float = Field(..., description="Quantity change (+ for increase, - for decrease). Cannot be zero.", examples=[-5.0])
    transaction_type: TransactionType = Field(..., description="Type of transaction (e.g., SALE, PURCHASE, ADJUSTMENT).", examples=["PROJECT_USAGE"])
    adjustment_type: Optional[InventoryAdjustmentType] = Field(None, description="Specific type if transaction_type is ADJUSTMENT.", examples=["DAMAGE"])
    reference_id: Optional[str] = Field(None, description="Optional related record ID (e.g., sale ID, project ID, purchase ID, count ID).", examples=["SALE_123", "PROJ_45"])
    reference_type: Optional[str] = Field(None, description="Type of the related record ('sale', 'project', 'purchase', 'count').", examples=["sale"])
    from_location: Optional[str] = Field(None, description="Source location identifier (for transfers).", examples=["Warehouse"])
    to_location: Optional[str] = Field(None, description="Destination location identifier (for transfers or adjustments affecting location).", examples=["Workshop"])
    notes: Optional[str] = Field(None, description="Additional notes about the transaction.", examples=["Used for Project XYZ"])
    performed_by: Optional[str] = Field(None, description="Identifier (e.g., user ID or name) of who performed the action.", examples=["user_10"])

    # Pydantic v2 style validator
    @field_validator('item_type')
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        valid_types = ["material", "product", "tool"]
        if v.lower() not in valid_types:
            raise ValueError(f"Item type must be one of: {', '.join(valid_types)}")
        return v.lower()

    @field_validator('quantity_change')
    @classmethod
    def check_quantity_change_not_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError('Transaction quantity_change cannot be zero')
        return v

    # Pydantic v2: Use root_validator for cross-field validation
    # @model_validator(mode='before') # or 'after' depending on when you need values
    # def check_adjustment_type(cls, values):
    #     # In Pydantic v2, accessing other fields within validators is different.
    #     # This might require a `model_validator` or careful handling in the service layer.
    #     # For simplicity, this validation might be better handled in the service layer.
    #     tx_type = values.get('transaction_type')
    #     adj_type = values.get('adjustment_type')
    #     if tx_type == TransactionType.ADJUSTMENT and adj_type is None:
    #         raise ValueError("Adjustment type is required for adjustment transactions")
    #     return values


# --- Create Schemas ---

class InventoryCreate(InventoryBase):
    """Schema for creating a new Inventory record."""
    # Inherits validation from InventoryBase
    pass


class InventoryTransactionCreate(InventoryTransactionBase):
    """Schema for creating a new Inventory Transaction."""
    # Inherits validation from InventoryTransactionBase
    # Cross-field validation (like adjustment_type dependency) might be better handled in the service
    pass


# --- Update Schemas ---

class InventoryUpdate(BaseModel):
    """Schema for updating Inventory info (Quantity, Status, Location)."""
    quantity: Optional[float] = Field(None, description="New quantity on hand.", ge=0.0)
    status: Optional[InventoryStatus] = Field(None, description="New inventory status.")
    storage_location: Optional[str] = Field(None, description="New storage location identifier.")


class InventoryTransactionUpdate(BaseModel):
    """Schema for updating limited fields of an Inventory Transaction (primarily notes)."""
    notes: Optional[str] = Field(None, description="Updated notes for the transaction.")


# --- Database Representation Schemas ---

class InventoryInDB(InventoryBase):
    """Schema representing Inventory data as stored in the DB."""
    id: int = Field(..., description="Unique Inventory record ID.")
    createdAt: Optional[datetime] = Field(None, description="Timestamp when the record was created.")
    updatedAt: Optional[datetime] = Field(None, description="Timestamp when the record was last updated.")

    class Config:
        from_attributes = True # Pydantic v2


class InventoryTransactionInDB(InventoryTransactionBase):
    """Schema representing Inventory Transaction data as stored in the DB."""
    id: int = Field(..., description="Unique Transaction record ID.")
    transaction_date: datetime = Field(..., description="Timestamp when the transaction occurred.")
    # created_by maps to performed_by in the Base schema

    class Config:
        from_attributes = True # Pydantic v2


# --- API Response Schemas ---

class InventoryResponse(InventoryInDB):
    """
    Schema for API responses containing Inventory data.
    Includes potentially enriched data like item name.
    """
    item_name: Optional[str] = Field(None, description="Name of the related Product, Material, or Tool.", examples=["Leather Wallet V1", "Rawhide Lace Spool"])
    # value: Optional[float] = Field(None, description="Estimated value (Quantity * Cost). Requires cost lookup.") # Calculation is better done in service/reporting
    # is_low_stock: Optional[bool] = Field(None, description="Derived field: True if status is LOW_STOCK or quantity <= reorder_point.") # Status field already covers this
    # reorder_point: Optional[float] = Field(None, description="Reorder point of the item (fetched from related item).") # Belongs to Product/Material details
    # storage_location_name: Optional[str] = Field(None, description="Name of the storage location (requires lookup).") # Enrichment happens in service/endpoint

    class Config:
        from_attributes = True


class InventoryTransactionResponse(InventoryTransactionInDB):
    """
    Schema for API responses containing Inventory Transaction data.
    Includes potentially enriched data.
    """
    item_name: Optional[str] = Field(None, description="Name of the related Product, Material, or Tool.", examples=["Leather Wallet V1"])
    transaction_type_display: Optional[str] = Field(None, description="Display name for transaction type.", examples=["Sale Adjustment"])
    adjustment_type_display: Optional[str] = Field(None, description="Display name for adjustment type.", examples=["Damaged Goods"])
    # value_change: Optional[float] = Field(None, description="Estimated value change (Quantity Change * Cost). Requires cost lookup.") # Calculation better in service/reporting

    class Config:
        from_attributes = True


# --- List Response Schemas ---

class InventoryListResponse(BaseModel): # Renamed for clarity
    """Schema for paginated list of Inventory items."""
    items: List[InventoryResponse]
    total: int = Field(..., description="Total number of inventory records matching query.")
    page: int = Field(..., description="Current page number.")
    size: int = Field(..., description="Number of items per page.")
    pages: int = Field(..., description="Total number of pages.")


class InventoryTransactionListResponse(BaseModel): # Renamed for clarity
    """Schema for paginated list of Inventory Transactions."""
    items: List[InventoryTransactionResponse]
    total: int = Field(..., description="Total number of transactions matching query.")
    page: int = Field(..., description="Current page number.")
    size: int = Field(..., description="Number of items per page.")
    pages: int = Field(..., description="Total number of pages.")


# --- Specific Request/Operation Schemas ---

class InventoryAdjustmentRequest(BaseModel):
    """Schema specifically for the /inventory/adjust endpoint input."""
    item_type: str = Field(..., description="Type of item ('product', 'material', 'tool').")
    item_id: int = Field(..., description="ID of the item.")
    quantity_change: float = Field(..., description="Adjustment quantity (+/-). Cannot be zero.")
    adjustment_type: InventoryAdjustmentType = Field(..., description="Type of adjustment.")
    reason: str = Field(..., description="Reason for the adjustment.")
    notes: Optional[str] = Field(None, description="Additional notes.")
    reference_id: Optional[str] = Field(None, description="Optional related reference ID.")
    reference_type: Optional[str] = Field(None, description="Optional related reference type.")
    # Location might be updated implicitly based on where adjustment happens or explicitly
    location: Optional[str] = Field(None, description="Optional location where adjustment occurs / new location.")


class InventoryTransferRequest(BaseModel):
    """Schema specifically for the /inventory/transfer endpoint input."""
    item_type: str = Field(..., description="Type of item ('product', 'material', 'tool').")
    item_id: int = Field(..., description="ID of the item.")
    quantity: float = Field(..., description="Quantity to transfer.", gt=0)
    from_location: str = Field(..., description="Source location identifier.")
    to_location: str = Field(..., description="Destination location identifier.")
    notes: Optional[str] = Field(None, description="Additional notes for the transfer.")


# --- Search & Report Schemas ---

class InventorySearchParams(BaseModel):
    """Schema for filtering Inventory listing endpoint (`GET /inventory`)."""
    status: Optional[str] = Field(None, description="Filter by inventory status (e.g., 'IN_STOCK').")
    location: Optional[str] = Field(None, description="Filter by storage location identifier.")
    item_type: Optional[str] = Field(None, description="Filter by item type ('product', 'material', 'tool').")
    search: Optional[str] = Field(None, description="Search term (applies to item name/SKU - requires JOIN in repo).")
    # Add other relevant filters if needed, e.g., min_quantity, max_quantity


class InventorySummaryResponse(BaseModel): # Renamed for clarity
    """
    Schema for the /inventory/summary endpoint response.
    Matches frontend InventorySummary type.
    """
    total_products: int = Field(..., description="Total number of distinct tracked products.")
    in_stock: int = Field(..., description="Number of distinct items currently in stock.")
    low_stock: int = Field(..., description="Number of distinct items currently in low stock status.")
    out_of_stock: int = Field(..., description="Number of distinct items currently out of stock.")
    total_value: float = Field(..., description="Total estimated value of all tracked inventory items.")
    average_margin: Optional[float] = Field(None, description="Average profit margin across all tracked products (if calculable).")
    needs_reorder: int = Field(..., description="Number of distinct items at or below their reorder point.")
    # Optional: Add counts for materials and tools if needed
    # total_materials: int
    # total_tools: int
    generated_at: datetime = Field(..., description="Timestamp when the summary was generated.")

    class Config:
        from_attributes = True


class StockLevelReport(BaseModel): # Kept name as it's specific report type
    """Schema for a more detailed stock level report."""
    report_type: str = Field("stock_level", description="Type of the report")
    generated_at: datetime = Field(..., description="Timestamp when the report was generated")
    filters_applied: Dict[str, Any] = Field(..., description="Filters used for this report")
    total_value: float = Field(..., description="Total estimated value of reported inventory")
    category_breakdown: Dict[str, Any] = Field(..., description="Breakdown by specified category (e.g., type, location, status)")
    low_stock_items: List[InventoryResponse] = Field(..., description="Items below their reorder point") # Use InventoryResponse
    out_of_stock_items: List[InventoryResponse] = Field(..., description="Items with zero or negative quantity") # Use InventoryResponse
    # Add more detailed breakdowns as needed
    items_by_location: Optional[Dict[str, int]] = Field(None, description="Count of distinct items per location")
    reorder_recommendations: Optional[List[Dict[str, Any]]] = Field(None, description="Suggested items and quantities to reorder")


# --- Compatibility Aliases ---
# Use these in endpoint signatures if needed for backward compatibility,
# but prefer using the more specific schema names above where possible.

class Inventory(InventoryResponse): # Alias for response_model in GET /inventory/{id} ?
    pass

class InventoryTransaction(InventoryTransactionResponse): # Alias for response_model in GET /inventory/transactions/{id} ?
    pass

class InventoryAdjustment(InventoryAdjustmentRequest): # Alias for request body in POST /inventory/adjust
    pass

# Note: Product-specific schemas (ProductCreate, ProductUpdate, ProductFilter, ProductResponse, ProductList)
# should reside in app/schemas/product.py (or similar) as they relate directly to the Product entity
# and its API endpoints (/products), not the generic inventory tracking (/inventory) endpoints.