# File: app/schemas/product.py
"""
Pydantic schemas for the Product entity.

Defines data structures for API request validation (Create, Update, Filter)
and response formatting (Response, List).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator, field_validator, Json # Use Json for JSON fields

# Import necessary Enums used in Product model
from app.db.models.enums import ProjectType, InventoryStatus

# --- Helper Schemas for Nested Structures ---

class CostBreakdownSchema(BaseModel):
    """Represents the cost breakdown structure."""
    # Define fields based on what you expect IN the JSON
    # These are examples, adjust to your actual JSON structure
    materials: Optional[float] = Field(0.0, description="Total cost of materials")
    labor: Optional[float] = Field(0.0, description="Total cost of labor")
    overhead: Optional[float] = Field(0.0, description="Allocated overhead costs")
    # You might have more detail within the JSON stored in the DB
    # If so, define nested models here. For API response, often totals are sufficient.

# --- Base Schema ---

class ProductBase(BaseModel):
    """Base schema with common Product fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the product", examples=["Minimalist Wallet"])
    sku: str = Field(..., max_length=100, description="Unique Stock Keeping Unit (SKU)", examples=["WAL-MIN-BLK-01"])
    product_type: Optional[ProjectType] = Field(None, description="Type or category of the product (e.g., WALLET, BAG)", examples=["WALLET"])
    description: Optional[str] = Field(None, description="Detailed description of the product")
    materials: Optional[List[str]] = Field(None, description="List of materials used (e.g., names or IDs)", examples=[ "Horween Chromexcel", "Ritza Tiger Thread 0.6mm" ]) # Representing as list of strings for API
    color: Optional[str] = Field(None, max_length=50, description="Primary color of the product", examples=["Black"])
    dimensions: Optional[str] = Field(None, max_length=100, description="Physical dimensions (e.g., '4 x 3 inches')", examples=["4 x 3 inches"])
    weight: Optional[float] = Field(None, description="Weight of the product (e.g., in grams or ounces)", ge=0)
    pattern_id: Optional[int] = Field(None, description="ID of the Pattern used to make this product", examples=[5])
    reorder_point: Optional[int] = Field(0, description="Inventory level at which to reorder", ge=0, examples=[5])
    selling_price: Optional[float] = Field(None, description="Price at which the product is sold", ge=0)
    total_cost: Optional[float] = Field(None, description="Calculated total cost to produce one unit", ge=0)
    thumbnail: Optional[str] = Field(None, max_length=255, description="URL or path to the product's thumbnail image")
    notes: Optional[str] = Field(None, description="Internal notes about the product")
    batch_number: Optional[str] = Field(None, max_length=50, description="Identifier for the production batch")
    customizations: Optional[List[str]] = Field(None, description="List of customizations applied", examples=["Monogram: JSD", "Thread Color: Red"]) # Representing as list of strings
    project_id: Optional[int] = Field(None, description="ID of the specific Project this product instance relates to (if applicable)")

    # Cost breakdown might be input during creation/update, or calculated
    cost_breakdown: Optional[CostBreakdownSchema] = Field(None, description="Breakdown of production costs") # Use helper schema

    # Pydantic v2 style validator for SKU
    @field_validator('sku')
    @classmethod
    def sku_must_be_uppercase_stripped(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('SKU cannot be empty')
        return v.strip().upper()

    # Pydantic v2 style validator for Name
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip()


# --- Schema for Creation ---

class ProductCreate(ProductBase):
    """Schema used for creating a new Product via the API."""
    # Add fields specifically needed ONLY during creation (if any)
    # Fields required on creation but optional later are handled by ProductBase
    name: str # Make required explicitly if not covered by Field(...) in Base
    sku: str  # Make required explicitly

    # Initial stock details (optional, handled by service)
    quantity: Optional[float] = Field(0.0, description="Initial quantity on hand (defaults to 0)", ge=0)
    storage_location: Optional[str] = Field(None, description="Initial storage location")


# --- Schema for Update ---

class ProductUpdate(BaseModel):
    """Schema used for updating an existing Product via the API. All fields are optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    product_type: Optional[ProjectType] = None
    description: Optional[str] = None
    materials: Optional[List[str]] = None
    color: Optional[str] = Field(None, max_length=50)
    dimensions: Optional[str] = Field(None, max_length=100)
    weight: Optional[float] = Field(None, ge=0)
    pattern_id: Optional[int] = None
    reorder_point: Optional[int] = Field(None, ge=0)
    selling_price: Optional[float] = Field(None, ge=0)
    total_cost: Optional[float] = Field(None, ge=0) # Allow updating calculated cost if needed, or remove if always calculated
    thumbnail: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    batch_number: Optional[str] = Field(None, max_length=50)
    customizations: Optional[List[str]] = None
    project_id: Optional[int] = None
    cost_breakdown: Optional[CostBreakdownSchema] = None

    # Pydantic v2 style validator for SKU
    @field_validator('sku')
    @classmethod
    def sku_must_be_uppercase_stripped(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if not v.strip(): raise ValueError('SKU cannot be empty if provided')
        return v.strip().upper()

    # Pydantic v2 style validator for Name
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        if not v.strip(): raise ValueError('Product name cannot be empty if provided')
        return v.strip()

    # Note: We do NOT include quantity, status, storage_location here
    # as those should be updated via InventoryService/adjustments.


# --- Schema for Filtering ---

class PriceRangeFilter(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class DateRangeFilter(BaseModel):
    # Use alias to match potential frontend query param naming like 'dateAddedRange[from]'
    from_val: Optional[str] = Field(None, alias="from", description="Start date YYYY-MM-DD")
    to: Optional[str] = Field(None, description="End date YYYY-MM-DD")

class ProductFilter(BaseModel):
    """Schema representing possible query parameters for filtering Products."""
    productType: Optional[List[str]] = Field(None, description="List of product types (enum names)")
    status: Optional[List[str]] = Field(None, description="List of inventory statuses (enum names)")
    priceRange: Optional[PriceRangeFilter] = Field(None, description="Min/Max selling price range")
    dateAddedRange: Optional[DateRangeFilter] = Field(None, description="Date range for product creation (createdAt)")
    searchQuery: Optional[str] = Field(None, description="Text search query (name, sku, description)")
    storageLocation: Optional[str] = Field(None, description="Storage location identifier")
    # Add more filters if needed: pattern_id, project_id, etc.

    class Config:
        populate_by_name = True # Allows query params like priceRange[min]


# --- Schema for API Response ---

class ProductResponse(ProductBase):
    """Schema for representing a Product in API responses."""
    id: int = Field(..., description="Unique Product ID")

    # Fields derived from Inventory relationship (populated by Product.to_dict or service)
    quantity: float = Field(..., description="Current quantity from inventory record")
    status: Optional[InventoryStatus] = Field(None, description="Current status from inventory record")
    storage_location: Optional[str] = Field(None, description="Current storage location from inventory record")

    # Calculated field (populated by hybrid property or service)
    profit_margin: Optional[float] = Field(None, description="Calculated profit margin percentage")

    # Timestamps and other DB fields
    last_sold: Optional[datetime] = Field(None, description="Timestamp of the last sale")
    sales_velocity: Optional[float] = Field(None, description="Indicator of sales frequency/volume")
    created_at: Optional[datetime] = Field(None, alias="createdAt") # Match ORM model attribute if using alias
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    class Config:
        from_attributes = True # Enable reading data from ORM objects
        # Optionally include populate_by_name if aliases like createdAt are used
        populate_by_name = True


# --- Schema for Paginated List Response ---

class ProductList(BaseModel):
    """Schema for the paginated response when listing products."""
    items: List[ProductResponse] = Field(..., description="List of products on the current page")
    total: int = Field(..., description="Total number of products matching the query")
    page: int = Field(..., description="Current page number (usually starts at 1 for display)")
    size: int = Field(..., description="Number of items per page (limit)")
    pages: int = Field(..., description="Total number of pages available")