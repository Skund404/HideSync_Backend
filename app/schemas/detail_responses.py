# File: app/schemas/detail_responses.py
"""
Detail response schemas for the HideSync API.

This module contains Pydantic models for detailed response models that include
related entities and calculated fields.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.schemas.customer import CustomerResponse
from app.schemas.material import MaterialResponse
from app.schemas.project import ProjectResponse, TimelineTaskResponse, ProjectComponentResponse
from app.schemas.sale import SaleResponse, SaleItemResponse
from app.schemas.supplier import SupplierResponse
from app.schemas.inventory import InventoryResponse


class CustomerWithSales(CustomerResponse):
    """
    Schema for customer information with their sales history.
    """
    sales: List[SaleResponse] = Field([], description="Sale history for this customer")
    total_spent: float = Field(..., description="Total amount spent by this customer")
    average_order_value: float = Field(..., description="Average order value")
    first_purchase_date: Optional[datetime] = Field(None, description="Date of first purchase")
    last_purchase_date: Optional[datetime] = Field(None, description="Date of most recent purchase")
    sales_count: int = Field(..., description="Total number of sales")

    class Config:
        orm_mode = True


class MaterialWithInventory(MaterialResponse):
    """
    Schema for material information with inventory details.
    """
    inventory: List[InventoryResponse] = Field([], description="Inventory records for this material")
    total_quantity: float = Field(..., description="Total quantity across all inventory records")
    total_value: float = Field(..., description="Total inventory value")
    storage_locations: List[str] = Field([], description="Storage locations containing this material")
    purchase_history_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of purchase history")
    usage_history_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of usage history")

    class Config:
        orm_mode = True


class ProjectWithDetails(ProjectResponse):
    """
    Schema for project information with components and timeline.
    """
    components: List[ProjectComponentResponse] = Field([], description="Components used in this project")
    timeline_tasks: List[TimelineTaskResponse] = Field([], description="Timeline tasks for this project")
    materials_summary: Optional[Dict[str, Any]] = Field(None, description="Summary of materials used")
    customer_details: Optional[Dict[str, Any]] = Field(None, description="Customer details if associated")
    related_sales: List[SaleResponse] = Field([], description="Sales related to this project")
    resource_allocation: Optional[Dict[str, Any]] = Field(None, description="Allocated resources")

    class Config:
        orm_mode = True


class SaleWithDetails(SaleResponse):
    """
    Schema for sale information with items and customer details.
    """
    items: List[SaleItemResponse] = Field([], description="Items included in the sale")
    customer: Optional[CustomerResponse] = Field(None, description="Customer information")
    related_projects: List[ProjectResponse] = Field([], description="Projects related to this sale")
    payment_history: Optional[List[Dict[str, Any]]] = Field(None, description="Payment history")
    shipping_details: Optional[Dict[str, Any]] = Field(None, description="Shipping details")
    profit_analysis: Optional[Dict[str, Any]] = Field(None, description="Profit analysis")

    class Config:
        orm_mode = True


class SupplierWithDetails(SupplierResponse):
    """
    Schema for supplier information with materials and ratings.
    """
    materials: List[MaterialResponse] = Field([], description="Materials supplied by this supplier")
    ratings: List[Dict[str, Any]] = Field([], description="Ratings for this supplier")
    purchase_history: List[Dict[str, Any]] = Field([], description="Purchase history summary")
    performance_metrics: Optional[Dict[str, Any]] = Field(None, description="Supplier performance metrics")
    contact_history: Optional[List[Dict[str, Any]]] = Field(None, description="Contact history")

    class Config:
        orm_mode = True


class InventoryWithHistory(InventoryResponse):
    """
    Schema for inventory information with transaction history.
    """
    transactions: List[Dict[str, Any]] = Field([], description="Transaction history")
    movement_history: List[Dict[str, Any]] = Field([], description="Movement history")
    stock_level_trend: Optional[List[Dict[str, Any]]] = Field(None, description="Stock level trend")
    usage_pattern: Optional[Dict[str, Any]] = Field(None, description="Usage pattern analysis")

    class Config:
        orm_mode = True